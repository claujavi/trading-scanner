from typing import Dict, Optional

import polars as pl

from ..indicators.trend import calc_ema, calc_sma, detect_cruce_ema
from ..models import ScanConfig


def _above_ma(df: pl.DataFrame, periodo: int, use_ema: bool) -> Optional[bool]:
    if df is None or df.is_empty() or "close" not in df.columns:
        return None
    series = calc_ema(df, periodo) if use_ema else calc_sma(df, periodo)
    values = series.to_list()
    close_values = df["close"].to_list()
    if not values or not close_values:
        return None
    last_ma = values[-1]
    last_close = close_values[-1]
    if last_ma is None or last_close is None:
        return None
    return float(last_close) > float(last_ma)


def _safe_cruce(df: Optional[pl.DataFrame], rapida: int, lenta: int) -> Optional[bool]:
    if df is None or df.is_empty():
        return None
    return detect_cruce_ema(df, rapida, lenta)


def detect_setup_timeframe(
    df_5m: Optional[pl.DataFrame],
    df_15m: Optional[pl.DataFrame],
    df_4h: Optional[pl.DataFrame],
    df_d: Optional[pl.DataFrame],
    config: ScanConfig,
) -> Dict[str, Optional[bool]]:
    return {
        "cruce_ema_921_5m": _safe_cruce(df_5m, config.ema_rapida, config.ema_media),
        "cruce_ema_921_15m": _safe_cruce(df_15m, config.ema_rapida, config.ema_media),
        "cruce_ema_921_4h": _safe_cruce(df_4h, config.ema_rapida, config.ema_media),
        "cruce_ema_921_d": _safe_cruce(df_d, config.ema_rapida, config.ema_media),
        "sobre_sma200": _above_ma(df_d, config.sma_tendencia, use_ema=False),
        "sobre_ema50": _above_ma(df_d, config.ema_lenta, use_ema=True),
    }
