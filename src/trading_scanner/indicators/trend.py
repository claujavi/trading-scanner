from typing import Optional
import polars as pl
import pandas as pd


def _to_pandas(df: pl.DataFrame) -> pd.DataFrame:
    if isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df


def calc_ema(df: pl.DataFrame, periodo: int) -> pl.Series:
    pdf = _to_pandas(df)
    if "close" not in pdf.columns:
        return pl.Series([], dtype=pl.Float64)
    close = pdf["close"].astype(float)
    ema = close.ewm(span=periodo, adjust=False).mean()
    return pl.Series(ema.values)


def calc_sma(df: pl.DataFrame, periodo: int) -> pl.Series:
    pdf = _to_pandas(df)
    if "close" not in pdf.columns:
        return pl.Series([], dtype=pl.Float64)
    close = pdf["close"].astype(float)
    sma = close.rolling(window=periodo, min_periods=1).mean()
    return pl.Series(sma.values)


def calc_vwap(df: pl.DataFrame) -> pl.Series:
    pdf = _to_pandas(df)
    for col in ("high", "low", "close", "volume"):
        if col not in pdf.columns:
            return pl.Series([], dtype=pl.Float64)
    typ = (pdf["high"].astype(float) + pdf["low"].astype(float) + pdf["close"].astype(float)) / 3.0
    vol = pdf["volume"].astype(float)
    cum_pv = (typ * vol).cumsum()
    cum_v = vol.cumsum()
    # avoid division by zero
    vwap = cum_pv / cum_v.replace(0, pd.NA)
    vwap = vwap.fillna(method="ffill").fillna(0.0)
    return pl.Series(vwap.values)


def detect_cruce_ema(df: pl.DataFrame, rapida: int, lenta: int) -> Optional[bool]:
    """True si la EMA rápida está actualmente por encima de la EMA lenta,
    False si está por debajo. Reporta la posición relativa actual, no si el
    cruce ocurrió recién en la última vela — antes de v1.1.0 exigía un cruce
    literal entre las dos últimas velas, lo que hacía que el criterio
    timeframe_setup casi nunca se pudiera calcular (0/3425 en el primer
    backtest real). None solo si no hay datos suficientes para calcular
    las EMAs, no si simplemente no hubo cruce."""
    pdf = _to_pandas(df)
    if "close" not in pdf.columns:
        return None
    close = pdf["close"].astype(float)
    if len(close) < 2:
        return None
    fast = close.ewm(span=rapida, adjust=False).mean()
    slow = close.ewm(span=lenta, adjust=False).mean()
    last_fast, last_slow = fast.iloc[-1], slow.iloc[-1]
    if last_fast is None or last_slow is None:
        return None
    return bool(last_fast > last_slow)
