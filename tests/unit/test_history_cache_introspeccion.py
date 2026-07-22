from datetime import date

from src.trading_scanner.config import settings
from src.trading_scanner.fetchers import history_cache


def _crear_parquet_falso(root, ticker, timeframe, year, month):
    carpeta = root / ticker / timeframe / str(year)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{month:02}.parquet").write_bytes(b"")


def test_tickers_cacheados_sin_carpeta_devuelve_vacio(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path / "no_existe")
    assert history_cache.tickers_cacheados() == []


def test_tickers_cacheados_lista_solo_los_que_tienen_parquet_del_timeframe(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    _crear_parquet_falso(tmp_path, "AAPL", "d", 2025, 1)
    _crear_parquet_falso(tmp_path, "TSLA", "5m", 2025, 1)  # sin "d" — no debe aparecer

    assert history_cache.tickers_cacheados("d") == ["AAPL"]


def test_rango_cacheado_sin_datos_devuelve_none(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    assert history_cache.rango_cacheado() is None


def test_rango_cacheado_calcula_min_y_max_entre_varios_tickers(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    _crear_parquet_falso(tmp_path, "AAPL", "d", 2024, 3)
    _crear_parquet_falso(tmp_path, "AAPL", "d", 2024, 4)
    _crear_parquet_falso(tmp_path, "TSLA", "d", 2026, 7)

    rango = history_cache.rango_cacheado("d")

    assert rango == (date(2024, 3, 1), date(2026, 7, 31))


def test_rango_cacheado_diciembre_calcula_fin_de_mes_correcto(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    _crear_parquet_falso(tmp_path, "AAPL", "d", 2025, 12)

    rango = history_cache.rango_cacheado("d")

    assert rango == (date(2025, 12, 1), date(2025, 12, 31))
