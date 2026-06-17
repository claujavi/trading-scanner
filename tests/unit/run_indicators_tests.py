import sys
import polars as pl

from src.trading_scanner.indicators.trend import calc_ema
from src.trading_scanner.indicators.volume import calc_atr


def test_ema_constant_series():
    n = 20
    df = pl.DataFrame({
        "open": [100.0] * n,
        "high": [100.0] * n,
        "low": [100.0] * n,
        "close": [100.0] * n,
        "volume": [1000] * n,
    })
    ema9 = calc_ema(df, 9)
    assert len(ema9) == n
    assert all(float(x) == 100.0 for x in ema9.to_list())


def test_atr_zero_range():
    n = 20
    df = pl.DataFrame({
        "open": [50.0] * n,
        "high": [50.0] * n,
        "low": [50.0] * n,
        "close": [50.0] * n,
        "volume": [500] * n,
    })
    atr = calc_atr(df, 14)
    assert len(atr) == n
    assert float(atr.to_list()[-1]) == 0.0


def main():
    tests = [test_ema_constant_series, test_atr_zero_range]
    for t in tests:
        try:
            t()
            print(f"ok: {t.__name__}")
        except AssertionError as e:
            print(f"FAIL: {t.__name__}: {e}")
            sys.exit(2)


if __name__ == "__main__":
    main()
