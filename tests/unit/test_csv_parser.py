from pathlib import Path

import pytest

from trading_scanner.ingest.csv_parser import parse_csv


FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def test_parse_csv_valid_sample():
    sample_path = FIXTURE_DIR / "sample_scan.csv"
    tickers = parse_csv(sample_path)

    assert len(tickers) == 5
    first = tickers[0]
    assert first.ticker == "AAPL"
    assert first.precio == 172.15
    assert first.variacion_diaria_pct == 1.23
    assert first.volumen_actual == 5_678_900
    assert first.atr_pct == 2.8
    assert first.relvol == 2.1
    assert first.volumen_promedio == 12_000_000


def test_parse_csv_missing_columns_raises_value_error(tmp_path):
    path = tmp_path / "missing_columns.csv"
    path.write_text("Symbol,Last,Volume,ATR%\nAAPL,172.15,5678900,2.8\n")

    with pytest.raises(ValueError, match="faltan columnas obligatorias"):
        parse_csv(path)


def test_parse_csv_empty_returns_empty_list(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("Symbol,Last,Change%,Volume,ATR%\n")

    tickers = parse_csv(path)

    assert tickers == []
