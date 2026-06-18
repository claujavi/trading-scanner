"""
Pipeline pre-market: orquesta la evaluación completa de cada ticker.

Flujo por ticker (en paralelo con asyncio.gather):
  1. schwab_history → velas 5m/15m/4h/d
  2. schwab_options → IVR
  3. calendar_client → warning + catalizadores
  4. signals → cruces EMA, sobre SMA200
  5. evaluator → ScanResult
  6. database → persistir
"""

import asyncio
import traceback
from datetime import date, datetime
from typing import Optional

import polars as pl
from rich.console import Console

from .config import settings
from .database import db
from .engine.evaluator import DatosTickerCompletos, evaluar
from .engine.signals import detect_setup_timeframe
from .fetchers import calendar_client, schwab_options
from .fetchers import schwab_history as schwab_hist
from .fetchers.mock_schwab import generate_ohlcv, get_mock_ivr
from .models import FuenteDatos, ScanConfig, ScanResult, TickerBasico

console = Console()

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


async def _fetch_ivr(ticker: str) -> Optional[float]:
    if settings.mock_schwab:
        return get_mock_ivr(ticker)
    return await asyncio.to_thread(schwab_options.get_ivr, ticker)


async def process_ticker(ticker_data: TickerBasico, config: ScanConfig) -> ScanResult:
    ticker = ticker_data.ticker

    (df_5m, df_15m, df_4h, df_d), ivr, warning = await asyncio.gather(
        _fetch_history(ticker, ticker_data.precio, config),
        _fetch_ivr(ticker),
        calendar_client.get_warning(ticker),
    )

    signals = detect_setup_timeframe(df_5m, df_15m, df_4h, df_d, config)

    relvol = ticker_data.relvol if ticker_data.relvol > 0 else None
    atr_pct = ticker_data.atr_pct if ticker_data.atr_pct > 0 else None

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
    )

    result = evaluar(datos, config)
    result = result.model_copy(update={"calendar_disponible": warning.disponible})

    try:
        await db.insert_scan_result(result)
    except Exception as exc:
        console.log(f"[red]Error persistiendo {ticker} en Turso: {exc}[/red]")

    return result


async def run_pipeline(
    tickers: list[TickerBasico], config: ScanConfig
) -> list[ScanResult]:
    if not tickers:
        return []

    console.log(f"[green]Pipeline iniciado: {len(tickers)} tickers[/green]")

    tasks = [process_ticker(t, config) for t in tickers]
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
