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
    pdf = _to_pandas(df)
    if "close" not in pdf.columns:
        return None
    close = pdf["close"].astype(float)
    fast = close.ewm(span=rapida, adjust=False).mean()
    slow = close.ewm(span=lenta, adjust=False).mean()
    diff = fast - slow
    if len(diff) < 2:
        return None
    prev, last = diff.iloc[-2], diff.iloc[-1]
    if prev < 0 and last > 0:
        return True
    if prev > 0 and last < 0:
        return False
    return None
