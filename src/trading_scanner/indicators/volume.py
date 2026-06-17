from typing import Optional
import polars as pl
import pandas as pd


def _to_pandas(df: pl.DataFrame) -> pd.DataFrame:
    if isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df


def calc_atr(df: pl.DataFrame, periodo: int = 14) -> pl.Series:
    pdf = _to_pandas(df)
    for col in ("high", "low", "close"):
        if col not in pdf.columns:
            return pl.Series([], dtype=pl.Float64)
    high = pdf["high"].astype(float)
    low = pdf["low"].astype(float)
    close = pdf["close"].astype(float)
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / periodo, adjust=False).mean()
    atr = atr.fillna(0.0)
    return pl.Series(atr.values)


def calc_atr_pct(df: pl.DataFrame, periodo: int = 14) -> pl.Series:
    atr = calc_atr(df, periodo)
    pdf = _to_pandas(df)
    if "close" not in pdf.columns or len(atr) == 0:
        return pl.Series([], dtype=pl.Float64)
    close = pdf["close"].astype(float)
    atr_pd = pd.Series(atr.to_list())
    atr_pct = (atr_pd / close) * 100.0
    atr_pct = atr_pct.fillna(0.0)
    return pl.Series(atr_pct.values)


def calc_relvol(df: pl.DataFrame, periodo: int = 50) -> float:
    pdf = _to_pandas(df)
    if "volume" not in pdf.columns or len(pdf) == 0:
        return 0.0
    vol = pdf["volume"].astype(float)
    window = vol.tail(periodo)
    if len(window) == 0:
        return 0.0
    avg = window.mean()
    if avg == 0:
        return 0.0
    current = vol.iloc[-1]
    return float(current / avg)


def calc_obv(df: pl.DataFrame) -> pl.Series:
    pdf = _to_pandas(df)
    for col in ("close", "volume"):
        if col not in pdf.columns:
            return pl.Series([], dtype=pl.Float64)
    close = pdf["close"].astype(float)
    vol = pdf["volume"].astype(float)
    sign = close.diff().fillna(0.0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (vol * sign).cumsum()
    return pl.Series(obv.values)
