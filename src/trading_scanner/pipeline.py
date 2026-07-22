"""
Pipeline pre-market: orquesta la evaluación completa de cada ticker.

Flujo por ticker (en paralelo con asyncio.gather):
  1. schwab_history → velas 5m/15m/4h/d
  2. indicators.volume → ATR%, RelVol, HV Rank (proxy de IVR)
  3. calendar_client → warning + catalizadores
  4. signals → cruces EMA, sobre SMA200
  5. evaluator → ScanResult
  6. database → persistir
"""

import asyncio
import json
import traceback
from datetime import date, datetime
from typing import Optional

import polars as pl
from rich.console import Console

from .config import settings
from .database import db
from .engine.evaluator import DatosTickerCompletos, evaluar
from .engine.signals import detect_setup_timeframe
from .fetchers import calendar_client
from .fetchers import schwab_history as schwab_hist
from .fetchers.market_data_cache import MarketDataCache
from .fetchers.mock_schwab import generate_ohlcv, get_mock_ivr
from .indicators.volume import calc_atr_pct, calc_avg_volume, calc_hv_rank, calc_relvol
from .models import FuenteDatos, ScanConfig, ScanResult, TickerBasico

console = Console()


async def get_active_config() -> ScanConfig:
    """Config activa: la última guardada desde /config en Turso, o los
    defaults de ScanConfig si todavía no se guardó ninguna. Se llama en
    cada scan (no una sola vez al arrancar) para que un cambio en /config
    aplique al próximo CSV sin reiniciar el servidor."""
    try:
        row = await db.get_latest_scan_config()
    except Exception:
        row = None
    if not row:
        return ScanConfig()
    snapshot = row.get("config_snapshot")
    data = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
    return ScanConfig(**data)

_EMPTY_DF = pl.DataFrame(schema={
    "timestamp": pl.Datetime("ms"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
})


async def _fetch_history(
    ticker: str, base_price: float, config: ScanConfig
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    if settings.mock_schwab:
        return (
            generate_ohlcv(ticker, config.velas_5m, "5m", base_price),
            generate_ohlcv(ticker, config.velas_15m, "15m", base_price),
            generate_ohlcv(ticker, config.velas_4h, "4h", base_price),
            generate_ohlcv(ticker, config.velas_diarias, "d", base_price),
        )
    try:
        results = await asyncio.gather(
            schwab_hist.get_history_async(ticker, "5m", config.velas_5m),
            schwab_hist.get_history_async(ticker, "15m", config.velas_15m),
            schwab_hist.get_history_async(ticker, "4h", config.velas_4h),
            schwab_hist.get_history_async(ticker, "d", config.velas_diarias),
        )
        return tuple(results)  # type: ignore[return-value]
    except Exception as exc:
        console.log(f"[red]Error historial {ticker}: {exc}[/red]")
        return _EMPTY_DF, _EMPTY_DF, _EMPTY_DF, _EMPTY_DF


def _calcular_ivr(ticker: str, df_d: pl.DataFrame, config: ScanConfig) -> Optional[float]:
    """Proxy de IVR. Schwab no expone el rango de 52 semanas de volatilidad
    implícita (solo la IV actual y el rango de 52 semanas de PRECIO), así
    que no se puede calcular un IV Rank real — se usa en su lugar HV Rank
    (volatilidad histórica de precio rankeada contra el último año, ver
    calc_hv_rank). En modo mock se mantiene el valor sintético de siempre.
    """
    if settings.mock_schwab:
        return get_mock_ivr(ticker)
    if df_d is None or df_d.is_empty():
        return None
    return calc_hv_rank(df_d, config.hv_periodo)


def _calcular_atr_pct(df_d: pl.DataFrame, periodo: int) -> Optional[float]:
    """ATR% calculado sobre velas diarias de Schwab — no depende de que el
    CSV de ToS incluya esa columna, y es el mismo cálculo que usaría el
    backtester (que no tiene CSV en absoluto)."""
    if df_d is None or df_d.is_empty():
        return None
    valores = calc_atr_pct(df_d, periodo).to_list()
    if not valores:
        return None
    ultimo = valores[-1]
    return float(ultimo) if ultimo not in (None, 0.0) else None


def _calcular_relvol(df_d: pl.DataFrame, periodo: int) -> Optional[float]:
    """RelVol calculado sobre velas diarias de Schwab — mismo motivo que
    _calcular_atr_pct: el CSV no está disponible en backtesting."""
    if df_d is None or df_d.is_empty():
        return None
    valor = calc_relvol(df_d, periodo)
    return valor if valor > 0 else None


def _calcular_volumen_promedio(df_d: pl.DataFrame, periodo: int) -> Optional[float]:
    """Volumen promedio para el filtro de entrada volumen_promedio_min —
    mismo motivo que _calcular_atr_pct/_calcular_relvol: el CSV no siempre
    trae la columna Avg Volume."""
    if df_d is None or df_d.is_empty():
        return None
    return calc_avg_volume(df_d, periodo)


async def process_ticker(
    ticker_data: TickerBasico, config: ScanConfig, cache: Optional[MarketDataCache] = None
) -> ScanResult:
    ticker = ticker_data.ticker

    (df_5m, df_15m, df_4h, df_d), warning = await asyncio.gather(
        _fetch_history(ticker, ticker_data.precio, config),
        calendar_client.get_warning(ticker),
    )

    signals = detect_setup_timeframe(df_5m, df_15m, df_4h, df_d, config)

    relvol = _calcular_relvol(df_d, config.relvol_periodo)
    atr_pct = _calcular_atr_pct(df_d, config.atr_periodo)
    ivr = _calcular_ivr(ticker, df_d, config)
    volumen_promedio = _calcular_volumen_promedio(df_d, config.relvol_periodo)

    datos = DatosTickerCompletos(
        ticker=ticker,
        fecha=date.today(),
        timestamp=datetime.utcnow(),
        fuente=FuenteDatos.MOCK if settings.mock_schwab else FuenteDatos.LIVE,
        precio=ticker_data.precio,
        variacion_diaria_pct=ticker_data.variacion_diaria_pct,
        relvol=relvol,
        atr_pct=atr_pct,
        volumen_actual=ticker_data.volumen_actual,
        sobre_sma200=signals.get("sobre_sma200"),
        sobre_ema50=signals.get("sobre_ema50"),
        cruce_ema_921_5m=signals.get("cruce_ema_921_5m"),
        cruce_ema_921_15m=signals.get("cruce_ema_921_15m"),
        cruce_ema_921_4h=signals.get("cruce_ema_921_4h"),
        cruce_ema_921_d=signals.get("cruce_ema_921_d"),
        ivr=ivr,
        warning_calendar=warning.nivel if warning.disponible else None,
        earnings_24h=warning.earnings_24h,
        evento_macro_24h=warning.evento_macro_24h,
        filing_8k_24h=warning.filing_8k_24h,
        upgrade_downgrade_24h=warning.upgrade_downgrade_24h,
        catalizador_detectado=warning.catalizador_detectado,
        volumen_promedio=volumen_promedio,
        bid=ticker_data.bid,
        ask=ticker_data.ask,
        sin_historial_schwab=df_d.is_empty(),
    )

    result = evaluar(datos, config)
    result = result.model_copy(update={"calendar_disponible": warning.disponible})

    try:
        await db.insert_scan_result(result)
    except Exception as exc:
        console.log(
            f"[red]Error persistiendo {ticker} en Turso: "
            f"{type(exc).__name__}: {exc or 'sin detalle'}[/red]"
        )

    if cache is not None:
        # Siembra el cache de streaming con los mismos DataFrames que ya
        # se trajeron acá arriba — no dispara ninguna llamada REST nueva.
        cache.seed(
            ticker_data=ticker_data,
            df_5m=df_5m, df_15m=df_15m, df_4h=df_4h, df_d=df_d,
            signals=signals,
            volumen_promedio=volumen_promedio,
            atr_pct=atr_pct,
            ivr=ivr,
            warning=warning,
        )

    return result


async def run_pipeline(
    tickers: list[TickerBasico], config: ScanConfig, cache: Optional[MarketDataCache] = None
) -> list[ScanResult]:
    if not tickers:
        return []

    console.log(f"[green]Pipeline iniciado: {len(tickers)} tickers[/green]")

    tasks = [process_ticker(t, config, cache) for t in tickers]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    results, errors = [], 0
    for item in raw:
        if isinstance(item, Exception):
            tb = "".join(traceback.format_exception(type(item), item, item.__traceback__))
            console.log(f"[red]Error en pipeline: {item}\n{tb}[/red]")
            errors += 1
        else:
            results.append(item)

    console.log(
        f"[green]Pipeline completo: {len(results)} ok"
        + (f", {errors} errores" if errors else "")
        + "[/green]"
    )
    return results
