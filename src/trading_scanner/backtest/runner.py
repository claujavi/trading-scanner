"""
runner.py — corre el evaluador + simulador contra datos históricos de
Schwab (vía history_cache, que cachea en Parquet) para un rango de fechas
y universo de tickers, con la ScanConfig dada.

No hay warning_calendar/catalizador histórico: el Trading Calendar solo
trackea su watchlist fijo (AAPL, NVDA, TSLA, MSFT, META, GOOGLE) — ninguno
de los tickers reales de scan lo tuvo nunca, ni en vivo ni históricamente.
Tampoco hay spread bid/ask histórico — Schwab no lo expone vía REST. Ambos
quedan en None, igual que el evaluador ya maneja datos faltantes en vivo:
catalizador queda en criterios_incompletos, spread simplemente no se evalúa.

Universo histórico — "real" vs lista manual:
ToS no permite exportar el Stock Hacker retroactivamente (ver CLAUDE.md,
"Cómo llega realmente el CSV"), así que el único universo día-por-día
fiel a lo que el trader vio en pantalla es el que surge de los CSV que
ya se guardaron en input/ e input/processed/ — ver `universo_real_csv()`.
Correr el backtest sobre una lista de tickers fija aplicada a todos los
días de un rango (la firma vieja `run_backtest(tickers, ...)`) mide algo
distinto: qué tan bien puntúa el evaluador sobre nombres ya sabidos como
volátiles, no el rendimiento esperado del sistema en vivo. Útil como
chequeo secundario, pero no como fuente para calibrar parámetros.
"""

import asyncio
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import polars as pl
from rich.console import Console

from ..engine.evaluator import DatosTickerCompletos, evaluar
from ..engine.signals import detect_setup_timeframe
from ..fetchers import history_cache
from ..indicators.volume import calc_hv_rank
from ..ingest.csv_parser import parse_csv
from ..models import BacktestRun, Clasificacion, FuenteDatos, ScanConfig
from ..pipeline import _calcular_atr_pct, _calcular_relvol, _calcular_volumen_promedio
from .metrics import ResultadoDia, calcular_metricas
from .simulator import simular

console = Console()

# Límite de concurrencia contra Schwab. Sin esto, un backtest con muchos
# tickers x muchos días lanza miles de conexiones simultáneas: en Windows
# el selector de asyncio tiene un tope bajo de file descriptors (revienta
# con "too many file descriptors in select()"), y Schwab devuelve 403
# (bloqueo del WAF/Akamai) ante ráfagas grandes de requests concurrentes.
#
# Cada tarea (_evaluar_ticker_dia) dispara internamente hasta 4-5 llamadas
# a Schwab en paralelo (d/4h/15m/5m + velas del día para la simulación), así
# que un límite de 5 tareas concurrentes ya implica ~20-25 conexiones Schwab
# simultáneas — suficiente margen bajo el límite de sockets de Windows y
# lejos del umbral que dispara el bloqueo de Schwab.
_SCHWAB_CONCURRENCY = asyncio.Semaphore(5)


def _dias_habiles(inicio: date, fin: date) -> list[date]:
    dias = []
    actual = inicio
    while actual <= fin:
        if actual.weekday() < 5:  # lunes-viernes; no se descuentan feriados en este MVP
            dias.append(actual)
        actual += timedelta(days=1)
    return dias


async def _evaluar_ticker_dia(
    ticker: str, fecha: date, config: ScanConfig
) -> Optional[ResultadoDia]:
    async with _SCHWAB_CONCURRENCY:
        return await _evaluar_ticker_dia_impl(ticker, fecha, config)


async def _evaluar_ticker_dia_impl(
    ticker: str, fecha: date, config: ScanConfig
) -> Optional[ResultadoDia]:
    fin_contexto = fecha - timedelta(days=1)
    inicio_contexto_d = fin_contexto - timedelta(days=int(config.velas_diarias * 1.6) + 10)
    inicio_contexto_intraday = fin_contexto - timedelta(days=15)

    try:
        df_d, df_4h, df_15m, df_5m = await asyncio.gather(
            history_cache.get_history(ticker, "d", inicio_contexto_d, fin_contexto),
            history_cache.get_history(ticker, "4h", inicio_contexto_intraday, fin_contexto),
            history_cache.get_history(ticker, "15m", inicio_contexto_intraday, fin_contexto),
            history_cache.get_history(ticker, "5m", inicio_contexto_intraday, fin_contexto),
        )
    except Exception as exc:
        console.log(f"[yellow]Backtest: sin historial de contexto para {ticker} {fecha}: {exc}[/yellow]")
        return None

    if df_d.is_empty() or df_d.height < 2:
        return None

    precio_hoy = float(df_d["close"][-1])
    precio_ayer = float(df_d["close"][-2])
    variacion_diaria_pct = (precio_hoy / precio_ayer - 1) * 100 if precio_ayer else 0.0
    volumen_actual = int(df_d["volume"][-1])

    signals = detect_setup_timeframe(df_5m, df_15m, df_4h, df_d, config)
    atr_pct = _calcular_atr_pct(df_d, config.atr_periodo)
    relvol = _calcular_relvol(df_d, config.relvol_periodo)
    volumen_promedio = _calcular_volumen_promedio(df_d, config.relvol_periodo)
    ivr = calc_hv_rank(df_d, config.hv_periodo)

    datos = DatosTickerCompletos(
        ticker=ticker,
        fecha=fecha,
        timestamp=datetime.combine(fecha, datetime.min.time()),
        fuente=FuenteDatos.HISTORICO,
        precio=precio_hoy,
        variacion_diaria_pct=variacion_diaria_pct,
        relvol=relvol,
        atr_pct=atr_pct,
        volumen_actual=volumen_actual,
        sobre_sma200=signals.get("sobre_sma200"),
        sobre_ema50=signals.get("sobre_ema50"),
        cruce_ema_921_5m=signals.get("cruce_ema_921_5m"),
        cruce_ema_921_15m=signals.get("cruce_ema_921_15m"),
        cruce_ema_921_4h=signals.get("cruce_ema_921_4h"),
        cruce_ema_921_d=signals.get("cruce_ema_921_d"),
        ivr=ivr,
        warning_calendar=None,
        earnings_24h=False,
        evento_macro_24h=False,
        filing_8k_24h=False,
        upgrade_downgrade_24h=False,
        catalizador_detectado=False,
        volumen_promedio=volumen_promedio,
        bid=None,
        ask=None,
    )

    result = evaluar(datos, config)

    simulacion = None
    if result.clasificacion in (Clasificacion.DAY, Clasificacion.SWING) and atr_pct:
        atr_valor = precio_hoy * atr_pct / 100.0
        try:
            velas_dia = await history_cache.get_history(ticker, "5m", fecha, fecha)
        except Exception:
            velas_dia = pl.DataFrame()
        if not velas_dia.is_empty():
            simulacion = simular(velas_dia, atr_valor, config)

    return result, simulacion


async def _recolectar(tareas: list) -> list[ResultadoDia]:
    """Lanza las tareas en paralelo, filtra excepciones y resultados None.
    Compartido por recolectar_resultados() y recolectar_resultados_universo_real()."""
    crudos = await asyncio.gather(*tareas, return_exceptions=True)

    resultados: list[ResultadoDia] = []
    errores = 0
    for item in crudos:
        if isinstance(item, Exception):
            errores += 1
        elif item is not None:
            resultados.append(item)

    console.log(
        f"[green]Backtest: {len(resultados)} evaluaciones"
        + (f", {errores} errores" if errores else "")
        + "[/green]"
    )
    return resultados


async def recolectar_resultados(
    tickers: list[str], fecha_inicio: date, fecha_fin: date, config: ScanConfig
) -> list[ResultadoDia]:
    """Evalúa+simula una lista fija de tickers contra todos los días hábiles
    del rango, con la config dada. Usado por run_backtest() y, directamente
    (sin pasar por calcular_metricas), por el optimizador para correr muchos
    trials sin construir un BacktestRun completo en cada uno."""
    dias = _dias_habiles(fecha_inicio, fecha_fin)
    console.log(
        f"[green]Backtest iniciado: {len(tickers)} tickers x {len(dias)} días hábiles[/green]"
    )
    tareas = [
        _evaluar_ticker_dia(ticker, fecha, config)
        for fecha in dias
        for ticker in tickers
    ]
    return await _recolectar(tareas)


async def run_backtest(
    tickers: list[str], fecha_inicio: date, fecha_fin: date, config: ScanConfig
) -> BacktestRun:
    resultados = await recolectar_resultados(tickers, fecha_inicio, fecha_fin, config)
    return calcular_metricas(config, fecha_inicio, fecha_fin, tickers, resultados)


# Fecha en el nombre de archivo del trader: scan_20260716.csv,
# scan_20260717_20260717_130741.csv (renombrado por csv_watcher al mover a
# processed/), sample_scan_*.csv (fixtures de prueba — se excluyen).
_FECHA_EN_NOMBRE = re.compile(r"(\d{8})")


def universo_real_csv(input_folder: Path) -> dict[date, list[str]]:
    """Reconstruye, para cada día que el trader efectivamente exportó un CSV
    de ToS, la lista real de tickers que salieron ese día — union de todos
    los CSV de esa fecha (el Stock Hacker puede agregar candidatos nuevos
    durante la sesión, ver CLAUDE.md "Descubrimiento incremental")."""
    carpetas = [input_folder, input_folder / "processed"]
    por_dia: dict[date, set[str]] = {}

    for carpeta in carpetas:
        if not carpeta.exists():
            continue
        for path in carpeta.glob("*.csv"):
            if path.stem.startswith("sample_"):
                continue
            match = _FECHA_EN_NOMBRE.search(path.stem)
            if not match:
                continue
            try:
                fecha = datetime.strptime(match.group(1), "%Y%m%d").date()
            except ValueError:
                continue
            try:
                tickers = [t.ticker for t in parse_csv(path)]
            except Exception as exc:
                console.log(f"[yellow]No se pudo parsear {path.name} para universo real: {exc}[/yellow]")
                continue
            por_dia.setdefault(fecha, set()).update(tickers)

    return {fecha: sorted(tks) for fecha, tks in sorted(por_dia.items())}


async def recolectar_resultados_universo_real(
    universo: dict[date, list[str]], config: ScanConfig
) -> list[ResultadoDia]:
    """Evalúa+simula el universo real (día → tickers que salieron ese día en
    un CSV guardado) con la config dada. Recibe `universo` ya calculado para
    que el optimizador lo compute una sola vez fuera del loop de trials
    (universo_real_csv() no depende de la config, solo de los CSV en disco)."""
    console.log(
        f"[green]Backtest universo real: {len(universo)} días con CSV guardado[/green]"
    )
    tareas = [
        _evaluar_ticker_dia(ticker, fecha, config)
        for fecha, tickers in universo.items()
        for ticker in tickers
    ]
    return await _recolectar(tareas)


async def run_backtest_universo_real(config: ScanConfig, input_folder: Path) -> BacktestRun:
    """Backtest fiel al universo real: cada ticker solo se evalúa los días
    en que efectivamente apareció en un CSV de ToS guardado por el trader —
    a diferencia de run_backtest(), que aplica una lista fija a todo el
    rango de fechas parejo."""
    universo = universo_real_csv(input_folder)
    if not universo:
        raise ValueError(
            "No hay CSV históricos guardados en input/ ni input/processed/ "
            "para reconstruir el universo real."
        )

    resultados = await recolectar_resultados_universo_real(universo, config)

    todos_tickers = sorted({t for tickers in universo.values() for t in tickers})
    fechas = sorted(universo.keys())
    return calcular_metricas(config, fechas[0], fechas[-1], todos_tickers, resultados)
