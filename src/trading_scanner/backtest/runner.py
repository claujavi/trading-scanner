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
"""

import asyncio
from datetime import date, datetime, timedelta
from typing import Optional

import polars as pl
from rich.console import Console

from ..engine.evaluator import DatosTickerCompletos, evaluar
from ..engine.signals import detect_setup_timeframe
from ..fetchers import history_cache
from ..indicators.volume import calc_hv_rank
from ..models import BacktestRun, Clasificacion, FuenteDatos, ScanConfig
from ..pipeline import _calcular_atr_pct, _calcular_relvol, _calcular_volumen_promedio
from .metrics import ResultadoDia, calcular_metricas
from .simulator import simular

console = Console()


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


async def run_backtest(
    tickers: list[str], fecha_inicio: date, fecha_fin: date, config: ScanConfig
) -> BacktestRun:
    dias = _dias_habiles(fecha_inicio, fecha_fin)
    console.log(
        f"[green]Backtest iniciado: {len(tickers)} tickers x {len(dias)} días hábiles[/green]"
    )

    tareas = [
        _evaluar_ticker_dia(ticker, fecha, config)
        for fecha in dias
        for ticker in tickers
    ]
    crudos = await asyncio.gather(*tareas, return_exceptions=True)

    resultados: list[ResultadoDia] = []
    errores = 0
    for item in crudos:
        if isinstance(item, Exception):
            errores += 1
        elif item is not None:
            resultados.append(item)

    console.log(
        f"[green]Backtest completo: {len(resultados)} evaluaciones"
        + (f", {errores} errores" if errores else "")
        + "[/green]"
    )

    return calcular_metricas(config, fecha_inicio, fecha_fin, tickers, resultados)
