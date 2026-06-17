from typing import Optional, Tuple
import polars as pl
import pandas as pd


def _to_pandas(df: pl.DataFrame) -> pd.DataFrame:
    if isinstance(df, pl.DataFrame):
        return df.to_pandas()
    return df


def calc_rsi(df: pl.DataFrame, periodo: int = 14) -> pl.Series:
    pdf = _to_pandas(df)
    if "close" not in pdf.columns:
        return pl.Series([], dtype=pl.Float64)
    close = pdf["close"].astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / periodo, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / periodo, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(100.0).replace(pd.NA, 0.0)
    return pl.Series(rsi.values)


def calc_macd(df: pl.DataFrame, rapida: int = 12, lenta: int = 26, signal: int = 9) -> Tuple[pl.Series, pl.Series, pl.Series]:
    pdf = _to_pandas(df)
    if "close" not in pdf.columns:
        return pl.Series([]), pl.Series([]), pl.Series([])
    close = pdf["close"].astype(float)
    ema_fast = close.ewm(span=rapida, adjust=False).mean()
    ema_slow = close.ewm(span=lenta, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pl.Series(macd_line.values), pl.Series(signal_line.values), pl.Series(hist.values)


def detect_cruce_macd(df: pl.DataFrame) -> Optional[bool]:
    macd, signal, _ = calc_macd(df)
    # convert to pandas for easy indexing
    if len(macd) < 2 or len(signal) < 2:
        return None
    macd_pd = pd.Series(macd.to_list())
    signal_pd = pd.Series(signal.to_list())
    prev_diff = macd_pd.iloc[-2] - signal_pd.iloc[-2]
    last_diff = macd_pd.iloc[-1] - signal_pd.iloc[-1]
    if prev_diff < 0 and last_diff > 0:
        return True
    if prev_diff > 0 and last_diff < 0:
        return False
    return None
