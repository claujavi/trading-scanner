"""
Generador de datos OHLCV sintéticos para desarrollo sin credenciales Schwab.

Los datos son reproducibles: el mismo ticker siempre genera la misma secuencia
(seeded por nombre de ticker). Útil para tests y demos locales.
"""

import hashlib
import random
from datetime import datetime, timedelta
from typing import Optional

import polars as pl


def _seed(ticker: str, salt: int = 0) -> int:
    return int(hashlib.md5(f"{ticker}{salt}".encode()).hexdigest()[:8], 16)


def generate_ohlcv(
    ticker: str,
    n_periods: int,
    timeframe: str,
    base_price: float = 150.0,
) -> pl.DataFrame:
    rng = random.Random(_seed(ticker))

    if timeframe == "5m":
        delta = timedelta(minutes=5)
    elif timeframe == "15m":
        delta = timedelta(minutes=15)
    elif timeframe == "4h":
        delta = timedelta(hours=4)
    else:
        delta = timedelta(days=1)

    now = datetime.utcnow().replace(second=0, microsecond=0)
    timestamps = [now - delta * (n_periods - i) for i in range(n_periods)]

    price = base_price
    opens, highs, lows, closes, volumes = [], [], [], [], []

    for _ in range(n_periods):
        change_pct = rng.gauss(0.0002, 0.012)
        open_ = price
        close = max(price * (1 + change_pct), 0.01)
        spread = abs(rng.gauss(0, 0.005)) * price
        high = max(open_, close) + spread
        low = min(open_, close) - spread
        volume = int(rng.uniform(300_000, 2_500_000))

        opens.append(round(open_, 2))
        highs.append(round(high, 2))
        lows.append(round(max(low, 0.01), 2))
        closes.append(round(close, 2))
        volumes.append(volume)
        price = close

    return pl.DataFrame({
        "timestamp": [t.replace(tzinfo=None) for t in timestamps],
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": [float(v) for v in volumes],
    }).with_columns(pl.col("timestamp").cast(pl.Datetime("ms")))


def get_mock_ivr(ticker: str) -> Optional[float]:
    rng = random.Random(_seed(ticker, salt=1))
    return round(rng.uniform(10.0, 80.0), 1)
