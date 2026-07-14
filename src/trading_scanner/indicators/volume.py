from typing import Optional
import numpy as np
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


def calc_relvol(df: pl.DataFrame, periodo: int) -> float:
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


def calc_avg_volume(df: pl.DataFrame, periodo: int) -> Optional[float]:
    """Volumen promedio de las últimas `periodo` velas — usado para validar
    el filtro de entrada volumen_promedio_min cuando el CSV de ToS no trae
    la columna Avg Volume (mismo problema que atr_pct/relvol)."""
    pdf = _to_pandas(df)
    if "volume" not in pdf.columns or len(pdf) == 0:
        return None
    vol = pdf["volume"].astype(float)
    window = vol.tail(periodo)
    if len(window) == 0:
        return None
    avg = window.mean()
    return float(avg) if avg > 0 else None


def calc_hv_rank(df: pl.DataFrame, periodo_hv: int = 20) -> Optional[float]:
    """Volatilidad histórica (realizada) de precio, rankeada contra el
    último año de datos disponibles — proxy de IV Rank.

    Schwab no expone el rango de 52 semanas de volatilidad IMPLÍCITA (solo
    la IV actual y el rango de 52 semanas de PRECIO), así que no se puede
    calcular un IV Rank real. Esto mide en cambio dónde está la
    volatilidad realizada de hoy (ventana de `periodo_hv` días) respecto
    al rango de volatilidad realizada del último año — mismo propósito
    práctico (bajo = calmo/day, alto = turbulento/swing), pero mirando
    hacia atrás en vez de la expectativa de opciones.
    """
    pdf = _to_pandas(df)
    if "close" not in pdf.columns or len(pdf) < periodo_hv + 2:
        return None
    close = pdf["close"].astype(float)
    log_ret = np.log(close / close.shift(1))
    hv = log_ret.rolling(window=periodo_hv).std().dropna()
    if len(hv) < 2:
        return None
    hv_min, hv_max = hv.min(), hv.max()
    if hv_max - hv_min == 0:
        return None
    return float((hv.iloc[-1] - hv_min) / (hv_max - hv_min) * 100)


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
