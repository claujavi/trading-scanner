from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

from ..models import ScanConfig
import polars as pl


@dataclass(frozen=True)
class SetupSignals:
    cruce_ema_921_5m: Optional[bool]
    cruce_ema_921_15m: Optional[bool]
    cruce_ema_921_4h: Optional[bool]
    cruce_ema_921_d: Optional[bool]
    sobre_sma200: Optional[bool]
    sobre_ema50: Optional[bool]


def _last_bool(df: pl.DataFrame, column: str) -> Optional[bool]:
    if column not in df.columns or df.height == 0:
        return None
    value = df[column].to_list()[-1]
    return None if value is None else bool(value)


def detect_setup_timeframe(
    df_5m: pl.DataFrame,
    df_15m: pl.DataFrame,
    df_4h: pl.DataFrame,
    df_d: pl.DataFrame,
    config: ScanConfig,
) -> Dict[str, Optional[bool]]:
    return {
        "cruce_ema_921_5m": _last_bool(df_5m, "cruce_ema_921_921"),
        "cruce_ema_921_15m": _last_bool(df_15m, "cruce_ema_921_921"),
        "cruce_ema_921_4h": _last_bool(df_4h, "cruce_ema_921_921"),
        "cruce_ema_921_d": _last_bool(df_d, "cruce_ema_921_921"),
        "sobre_sma200": _last_bool(df_d, "sobre_sma200"),
        "sobre_ema50": _last_bool(df_d, "sobre_ema50"),
    }
