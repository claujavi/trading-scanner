import asyncio
from datetime import date
from pathlib import Path

import pytest

import src.trading_scanner.optimizer.universo as universo_module
from src.trading_scanner.models import ScanConfig
from src.trading_scanner.optimizer.universo import universo_curado, universo_real


def test_universo_real_sin_csv_lanza_value_error(monkeypatch):
    monkeypatch.setattr(universo_module, "universo_real_csv", lambda input_folder: {})

    with pytest.raises(ValueError):
        universo_real(Path("input"))


def test_universo_real_con_csv_arma_fuente_con_metadata_correcta(monkeypatch):
    universo = {
        date(2026, 1, 5): ["AAA", "BBB"],
        date(2026, 1, 6): ["BBB", "CCC"],
    }
    monkeypatch.setattr(universo_module, "universo_real_csv", lambda input_folder: universo)

    async def fake_recolectar(universo_arg, config):
        assert universo_arg is universo
        return []

    monkeypatch.setattr(universo_module, "recolectar_resultados_universo_real", fake_recolectar)

    fuente = universo_real(Path("input"))

    assert fuente.tickers == ["AAA", "BBB", "CCC"]
    assert fuente.fecha_inicio == date(2026, 1, 5)
    assert fuente.fecha_fin == date(2026, 1, 6)

    resultado = asyncio.run(fuente.recolectar(ScanConfig()))
    assert resultado == []


def test_universo_curado_sin_tickers_lanza_value_error():
    with pytest.raises(ValueError):
        universo_curado([], date(2026, 1, 1), date(2026, 2, 1))


def test_universo_curado_fecha_inicio_posterior_a_fin_lanza_value_error():
    with pytest.raises(ValueError):
        universo_curado(["AAPL"], date(2026, 2, 1), date(2026, 1, 1))


def test_universo_curado_arma_fuente_con_metadata_correcta(monkeypatch):
    async def fake_recolectar(tickers, fecha_inicio, fecha_fin, config):
        assert tickers == ["AAPL", "TSLA"]
        assert fecha_inicio == date(2026, 1, 1)
        assert fecha_fin == date(2026, 2, 1)
        return []

    monkeypatch.setattr(universo_module, "recolectar_resultados", fake_recolectar)

    fuente = universo_curado(["TSLA", "AAPL"], date(2026, 1, 1), date(2026, 2, 1))

    assert fuente.tickers == ["AAPL", "TSLA"]
    assert fuente.fecha_inicio == date(2026, 1, 1)
    assert fuente.fecha_fin == date(2026, 2, 1)

    resultado = asyncio.run(fuente.recolectar(ScanConfig()))
    assert resultado == []
