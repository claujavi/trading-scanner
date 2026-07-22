import asyncio
from datetime import datetime, timedelta

import pytest

import src.trading_scanner.fetchers.schwab_history as schwab_history


class FakeDb:
    """Reemplaza database.db en memoria — sin red, sin Turso real."""

    def __init__(self):
        self.filas: dict[tuple[str, str], dict] = {}
        self.marcadas: list[tuple[str, str, str]] = []

    async def get_tickers_sin_historial(self) -> list[dict]:
        return list(self.filas.values())

    async def marcar_ticker_sin_historial(self, ticker: str, timeframe: str, motivo: str) -> None:
        self.marcadas.append((ticker, timeframe, motivo))
        self.filas[(ticker, timeframe)] = {
            "ticker": ticker,
            "timeframe": timeframe,
            "motivo": motivo,
            "verificado_en": datetime.utcnow().isoformat(),
        }


@pytest.fixture(autouse=True)
def _reset_cache_en_memoria(monkeypatch):
    """El cache en memoria de schwab_history.py es un global de módulo —
    resetearlo entre tests para que no se filtren entre sí."""
    monkeypatch.setattr(schwab_history, "_sin_historial_cache", None)
    fake_db = FakeDb()
    monkeypatch.setattr(schwab_history, "db", fake_db)
    return fake_db


def test_primera_falla_definitiva_se_marca_y_relanza(monkeypatch):
    def _get_history_falla(ticker, timeframe, n_periods):
        raise RuntimeError("No se pudo parsear el historial de Schwab: respuesta vacía")

    monkeypatch.setattr(schwab_history, "get_history", _get_history_falla)
    fake_db = schwab_history.db

    async def body():
        with pytest.raises(RuntimeError):
            await schwab_history.get_history_async("AXIApC", "d", 252)

    asyncio.run(body())
    assert ("AXIApC", "d", "No se pudo parsear el historial de Schwab: respuesta vacía") in fake_db.marcadas


def test_segunda_llamada_no_vuelve_a_golpear_schwab(monkeypatch):
    llamadas = []

    def _get_history_falla(ticker, timeframe, n_periods):
        llamadas.append(1)
        raise RuntimeError("No se pudo parsear el historial de Schwab: respuesta vacía")

    monkeypatch.setattr(schwab_history, "get_history", _get_history_falla)

    async def body():
        with pytest.raises(RuntimeError):
            await schwab_history.get_history_async("AXIApC", "d", 252)
        with pytest.raises(RuntimeError, match="cache negativo"):
            await schwab_history.get_history_async("AXIApC", "d", 252)

    asyncio.run(body())
    assert len(llamadas) == 1  # la segunda vez no llamó a get_history() real


def test_error_transitorio_no_se_cachea(monkeypatch):
    def _get_history_falla_transitorio(ticker, timeframe, n_periods):
        raise RuntimeError("Error al descargar historial Schwab: 500 Internal Server Error")

    monkeypatch.setattr(schwab_history, "get_history", _get_history_falla_transitorio)
    fake_db = schwab_history.db

    async def body():
        with pytest.raises(RuntimeError, match="500"):
            await schwab_history.get_history_async("AAPL", "d", 252)

    asyncio.run(body())
    assert fake_db.marcadas == []


def test_ttl_vencido_reintenta_contra_schwab(monkeypatch):
    fake_db = schwab_history.db
    vencido = datetime.utcnow() - timedelta(days=31)
    fake_db.filas[("AXIApC", "d")] = {
        "ticker": "AXIApC",
        "timeframe": "d",
        "motivo": "vieja",
        "verificado_en": vencido.isoformat(),
    }

    llamadas = []

    def _get_history_ok(ticker, timeframe, n_periods):
        llamadas.append(1)
        raise RuntimeError("No se pudo parsear el historial de Schwab: respuesta vacía")

    monkeypatch.setattr(schwab_history, "get_history", _get_history_ok)

    async def body():
        with pytest.raises(RuntimeError):
            await schwab_history.get_history_async("AXIApC", "d", 252)

    asyncio.run(body())
    assert len(llamadas) == 1  # el TTL venció, sí reintentó contra "Schwab"
