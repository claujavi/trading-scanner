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

import pandas as pd
import polars as pl

from ..engine.evaluator import DatosTickerCompletos, evaluar
from ..fetchers import history_cache
from ..indicators.volume import calc_hv_rank
from ..ingest.csv_parser import parse_csv
from ..logging_setup import console
from ..models import BacktestRun, Clasificacion, FuenteDatos, ScanConfig
from ..pipeline import _calcular_relvol, _calcular_volumen_promedio
from .metrics import ResultadoDia, calcular_metricas
from .simulator import simular

# Límite de concurrencia. Antes acotaba tareas por (ticker, día) — con un
# universo curado de años x cientos de tickers eso son cientos de miles de
# tareas, cada una releyendo y reconcatenando los mismos Parquet del ticker
# una vez por día evaluado (ver historial de perf: un run de 287 tickers x
# ~930 días hábiles tardó >22hs sin terminar ni el primer trial de 50). Desde
# que la unidad de concurrencia pasó a ser el ticker (ver
# _evaluar_ticker_para_dias más abajo, que carga el contexto de cada
# ticker UNA sola vez y después recorre sus días en memoria), este límite ya
# no protege contra una explosión de tareas — solo sigue siendo relevante
# para no abrir demasiadas conexiones reales a Schwab si el cache está
# incompleto y hace falta ir a la red. Mismo valor de siempre (5) por eso:
# ~4-5 llamadas Schwab por ticker si hay cache miss, 5 tickers concurrentes
# ≈ 20-25 conexiones, el mismo margen ya validado contra el bloqueo 403.
_SCHWAB_CONCURRENCY = asyncio.Semaphore(5)


def _dias_habiles(inicio: date, fin: date) -> list[date]:
    dias = []
    actual = inicio
    while actual <= fin:
        if actual.weekday() < 5:  # lunes-viernes; no se descuentan feriados en este MVP
            dias.append(actual)
        actual += timedelta(days=1)
    return dias


def _a_pandas_indexado(df: pl.DataFrame) -> pd.DataFrame:
    """Convierte una sola vez por ticker (no una vez por día) a pandas con
    índice de tiempo ordenado — las funciones de indicators/trend.py y
    indicators/volume.py ya aceptan pandas directamente sin re-convertir
    (`_to_pandas()` solo convierte si recibe un pl.DataFrame; si ya es
    pandas, lo devuelve tal cual). Antes, cada una de las ~933 evaluaciones
    por ticker recortaba con Polars y cada función de indicador volvía a
    convertir esa porción a pandas — con años de historial x cientos de
    tickers, esa conversión repetida (933 días x ~8 conversiones por día)
    era el costo de CPU dominante de un trial. Recortar ventanas de un
    DataFrame pandas ya indexado por fecha es muchísimo más barato."""
    if df.is_empty():
        return pd.DataFrame(columns=df.columns)
    pdf = df.to_pandas()
    pdf = pdf.set_index("timestamp").sort_index()
    return pdf


def _recortar_pandas(pdf: pd.DataFrame, inicio: date, fin: date) -> pd.DataFrame:
    """Misma selección que history_cache.filter_range() (>= inicio, <= fin,
    por fecha) pero sobre un DataFrame pandas ya indexado por tiempo —
    resultado idéntico, solo más barato de recortar repetidamente.

    No resetea el índice (a diferencia de una versión anterior): lo único
    que consume este recorte hoy es calc_relvol/calc_avg_volume/calc_hv_rank
    (vía _evaluar_dia_desde_cache), y ninguna de esas combina Series por
    alineación de índice entre sí (operan sobre una sola columna, o hacen
    `.shift()` que preserva el índice de origen) — a diferencia de
    calc_atr_pct, que sí lo necesitaba y por eso ya no pasa por acá (ver
    _serie_atr_pct, vectorizada aparte sobre la serie completa). Si algún
    día se vuelve a rutear una función con ese patrón por este recorte, el
    test de equivalencia lo va a agarrar (daría NaN, no un número
    silenciosamente distinto)."""
    if pdf.empty:
        return pdf
    return pdf.loc[pd.Timestamp(inicio) : pd.Timestamp(fin) + timedelta(days=1) - timedelta(microseconds=1)]


def _valor_asof(serie: pd.Series, dia: date):
    """Último valor de una serie ya indexada por fecha, en o antes de `dia`
    (equivalente a "el valor de ayer" cuando `dia` = fin_contexto) — None si
    todavía no hay ningún dato a esa altura (mismo caso que hoy devuelve
    None por datos insuficientes)."""
    if serie.empty:
        return None
    valor = serie.asof(pd.Timestamp(dia))
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    return valor


def _serie_cruce_ema(pdf_full: pd.DataFrame, rapida: int, lenta: int) -> pd.Series:
    """Serie completa de "EMA rápida > EMA lenta", calculada una sola vez
    sobre todo el historial del ticker — reemplaza a detect_cruce_ema()
    recalculado por día. Misma fórmula exacta que
    indicators/trend.py::detect_cruce_ema (`close.ewm(span=X,
    adjust=False).mean()`); un test de equivalencia (
    test_runner_equivalencia_pandas.py) verifica que da lo mismo que el
    camino viejo. Matemáticamente válido vectorizar: EMA converge (la
    influencia del punto de partida decae exponencialmente) mucho antes de
    los ~400 días de contexto que ya se usaban por día, así que el valor en
    cualquier fecha es el mismo la calcule con todo el historial o con la
    ventana acotada de siempre."""
    if pdf_full.empty or "close" not in pdf_full.columns:
        return pd.Series(dtype=object)
    close = pdf_full["close"].astype(float)
    fast = close.ewm(span=rapida, adjust=False).mean()
    slow = close.ewm(span=lenta, adjust=False).mean()
    cruce = (fast > slow).astype(object)
    cruce.iloc[0] = None  # detect_cruce_ema exige len(close) >= 2
    return cruce


def _serie_sobre_ma(pdf_full: pd.DataFrame, periodo: int, use_ema: bool) -> pd.Series:
    """Serie completa de "close > media móvil", una sola vez — misma
    fórmula que indicators/trend.py::calc_ema/calc_sma. SMA
    (`rolling(window=N)`) ya depende solo de las últimas N filas sea cual
    sea el largo total pasado, así que vectorizar no cambia nada ahí; EMA
    converge igual que en _serie_cruce_ema."""
    if pdf_full.empty or "close" not in pdf_full.columns:
        return pd.Series(dtype=object)
    close = pdf_full["close"].astype(float)
    ma = (
        close.ewm(span=periodo, adjust=False).mean()
        if use_ema
        else close.rolling(window=periodo, min_periods=1).mean()
    )
    return close > ma


def _serie_atr_pct(pdf_full: pd.DataFrame, periodo: int) -> pd.Series:
    """Serie completa de ATR%, una sola vez — misma fórmula exacta que
    indicators/volume.py::calc_atr/calc_atr_pct (True Range + EWM con
    alpha=1/periodo). Converge igual que EMA por el mismo motivo."""
    if pdf_full.empty:
        return pd.Series(dtype=float)
    for col in ("high", "low", "close"):
        if col not in pdf_full.columns:
            return pd.Series(dtype=float)
    high = pdf_full["high"].astype(float)
    low = pdf_full["low"].astype(float)
    close = pdf_full["close"].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / periodo, adjust=False).mean().fillna(0.0)
    atr_pct = (atr / close * 100.0).fillna(0.0)
    return atr_pct


def _evaluar_dia_desde_cache(
    ticker: str,
    fecha: date,
    config: ScanConfig,
    pdf_d_full: pd.DataFrame,
    series_precalculadas: dict,
    df_5m_full: pl.DataFrame,
) -> Optional[ResultadoDia]:
    """Misma lógica de evaluación que antes (un día = un contexto terminado
    el día anterior). Dos caminos distintos según el indicador:

    - cruce_ema (4 timeframes), sobre_sma200/sobre_ema50 y atr_pct: se
      calcularon UNA sola vez para todo el ticker en _evaluar_ticker_para_dias
      (`series_precalculadas`, ver _serie_cruce_ema/_serie_sobre_ma/
      _serie_atr_pct) — acá solo se busca el valor de "ayer" con
      _valor_asof(). Matemáticamente idéntico a recalcular la ventana de
      ~400 días por día (EMA/ATR convergen mucho antes de esa ventana, ver
      test_runner_equivalencia_pandas.py), pero sin repetir el cálculo 933
      veces.
    - relvol, volumen_promedio y HV rank (IVR): siguen recortando la
      ventana de "d" por día, sin cambios — HV rank en particular rankea
      contra TODA la ventana que se le pase (no una ventana fija), así que
      vectorizarlo cambiaría el resultado, no solo la velocidad."""
    fin_contexto = fecha - timedelta(days=1)
    inicio_contexto_d = fin_contexto - timedelta(days=int(config.velas_diarias * 1.6) + 10)

    df_d = _recortar_pandas(pdf_d_full, inicio_contexto_d, fin_contexto)
    if df_d.empty or len(df_d) < 2:
        return None

    precio_hoy = float(df_d["close"].iloc[-1])
    precio_ayer = float(df_d["close"].iloc[-2])
    variacion_diaria_pct = (precio_hoy / precio_ayer - 1) * 100 if precio_ayer else 0.0
    volumen_actual = int(df_d["volume"].iloc[-1])

    signals = {
        "cruce_ema_921_5m": _valor_asof(series_precalculadas["cruce_5m"], fin_contexto),
        "cruce_ema_921_15m": _valor_asof(series_precalculadas["cruce_15m"], fin_contexto),
        "cruce_ema_921_4h": _valor_asof(series_precalculadas["cruce_4h"], fin_contexto),
        "cruce_ema_921_d": _valor_asof(series_precalculadas["cruce_d"], fin_contexto),
        "sobre_sma200": _valor_asof(series_precalculadas["sobre_sma200"], fin_contexto),
        "sobre_ema50": _valor_asof(series_precalculadas["sobre_ema50"], fin_contexto),
    }
    for clave in ("cruce_ema_921_5m", "cruce_ema_921_15m", "cruce_ema_921_4h", "cruce_ema_921_d", "sobre_sma200", "sobre_ema50"):
        if signals[clave] is not None:
            signals[clave] = bool(signals[clave])

    atr_pct = _valor_asof(series_precalculadas["atr_pct"], fin_contexto)
    if atr_pct is not None:
        atr_pct = float(atr_pct) if atr_pct not in (None, 0.0) else None
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
        velas_dia = history_cache.filter_range(df_5m_full, fecha, fecha)
        if not velas_dia.is_empty():
            simulacion = simular(velas_dia, atr_valor, config)

    return result, simulacion


async def _evaluar_ticker_para_dias(
    ticker: str, dias: list[date], config: ScanConfig
) -> list[ResultadoDia]:
    """Evalúa un ticker en varios días cargando su historial de contexto una
    sola vez (no una vez por día) — antes, cada día evaluado releía y
    reconcataba los mismos Parquet del ticker desde disco, lo que sobre un
    rango de años se vuelve un cuello de botella severo (ver comentario de
    _SCHWAB_CONCURRENCY)."""
    if not dias:
        return []

    dias_ordenados = sorted(dias)
    fin_max = dias_ordenados[-1] - timedelta(days=1)
    inicio_d = dias_ordenados[0] - timedelta(days=int(config.velas_diarias * 1.6) + 10)

    # El intradía (4h/15m/5m) solo existe en Schwab desde ~nov-2025 (ver
    # CLAUDE.md, "Precarga masiva del cache" — probado empíricamente, Schwab
    # trunca en silencio cualquier pedido más viejo que eso). Acotar el
    # pedido a ese piso evita disparar una llamada real a Schwab por cada
    # ticker pidiendo años de intradía que nunca van a existir cuando el
    # rango evaluado arranca antes de esa fecha (ej. universo curado desde
    # 2023) — antes quedaba oculto porque Schwab respondía con datos
    # truncados sin error; con eso el pedido simplemente no aporta nada útil.
    piso_intraday = history_cache.FECHA_INICIO_DEFAULT["5m"]
    inicio_intraday = max(dias_ordenados[0] - timedelta(days=15), piso_intraday)
    hay_intraday = fin_max >= piso_intraday

    async def _pedir_intraday(timeframe: str, fecha_fin: date) -> pl.DataFrame:
        if not hay_intraday:
            return pl.DataFrame()
        return await history_cache.get_history(ticker, timeframe, inicio_intraday, fecha_fin)

    async with _SCHWAB_CONCURRENCY:
        try:
            df_d_full, df_4h_full, df_15m_full, df_5m_full = await asyncio.gather(
                history_cache.get_history(ticker, "d", inicio_d, fin_max),
                _pedir_intraday("4h", fin_max),
                _pedir_intraday("15m", fin_max),
                _pedir_intraday("5m", dias_ordenados[-1]),
            )
        except Exception as exc:
            console.log(f"[yellow]Backtest: sin historial de contexto para {ticker}: {exc}[/yellow]")
            return []

    pdf_d_full = _a_pandas_indexado(df_d_full)
    pdf_4h_full = _a_pandas_indexado(df_4h_full)
    pdf_15m_full = _a_pandas_indexado(df_15m_full)
    pdf_5m_full = _a_pandas_indexado(df_5m_full)

    # Calculadas UNA sola vez para todo el ticker (no una vez por día) —
    # ver _evaluar_dia_desde_cache para el porqué de cuáles sí y cuáles no.
    series_precalculadas = {
        "cruce_5m": _serie_cruce_ema(pdf_5m_full, config.ema_rapida, config.ema_media),
        "cruce_15m": _serie_cruce_ema(pdf_15m_full, config.ema_rapida, config.ema_media),
        "cruce_4h": _serie_cruce_ema(pdf_4h_full, config.ema_rapida, config.ema_media),
        "cruce_d": _serie_cruce_ema(pdf_d_full, config.ema_rapida, config.ema_media),
        "sobre_sma200": _serie_sobre_ma(pdf_d_full, config.sma_tendencia, use_ema=False),
        "sobre_ema50": _serie_sobre_ma(pdf_d_full, config.ema_lenta, use_ema=True),
        "atr_pct": _serie_atr_pct(pdf_d_full, config.atr_periodo),
    }

    resultados: list[ResultadoDia] = []
    for fecha in dias_ordenados:
        resultado = _evaluar_dia_desde_cache(
            ticker, fecha, config, pdf_d_full, series_precalculadas, df_5m_full,
        )
        if resultado is not None:
            resultados.append(resultado)
    return resultados


async def _recolectar_por_ticker(tareas: list) -> list[ResultadoDia]:
    """Lanza una tarea por ticker (cada una cubre todos sus días en memoria),
    aplana los resultados y filtra excepciones. Compartido por
    recolectar_resultados() y recolectar_resultados_universo_real()."""
    crudos = await asyncio.gather(*tareas, return_exceptions=True)

    resultados: list[ResultadoDia] = []
    errores = 0
    for item in crudos:
        if isinstance(item, Exception):
            errores += 1
        else:
            resultados.extend(item)

    console.log(
        f"[green]Backtest: {len(resultados)} evaluaciones"
        + (f", {errores} tickers con error" if errores else "")
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
    tareas = [_evaluar_ticker_para_dias(ticker, dias, config) for ticker in tickers]
    return await _recolectar_por_ticker(tareas)


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
    por_ticker: dict[str, list[date]] = {}
    for fecha, tickers in universo.items():
        for ticker in tickers:
            por_ticker.setdefault(ticker, []).append(fecha)

    console.log(
        f"[green]Backtest universo real: {len(universo)} días con CSV guardado, "
        f"{len(por_ticker)} tickers[/green]"
    )
    tareas = [_evaluar_ticker_para_dias(ticker, dias, config) for ticker, dias in por_ticker.items()]
    return await _recolectar_por_ticker(tareas)


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
