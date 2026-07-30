import asyncio
from datetime import date, datetime, timedelta

import polars as pl

from src.trading_scanner.backtest import runner
from src.trading_scanner.fetchers import history_cache
from src.trading_scanner.models import ScanConfig


def _ohlcv(fecha_inicio: date, n: int, freq_minutos: int) -> pl.DataFrame:
    timestamps = [
        datetime.combine(fecha_inicio, datetime.min.time()) + timedelta(minutes=freq_minutos * i)
        for i in range(n)
    ]
    precios = [100.0 + (i % 10) * 0.5 for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": precios,
            "high": [p + 1 for p in precios],
            "low": [p - 1 for p in precios],
            "close": precios,
            "volume": [1000.0 + i for i in range(n)],
        }
    )


def _dias_habiles(inicio: date, fin: date) -> list[date]:
    dias = []
    actual = inicio
    while actual <= fin:
        if actual.weekday() < 5:
            dias.append(actual)
        actual += timedelta(days=1)
    return dias


def test_evaluar_ticker_para_dias_pide_history_una_sola_vez_por_timeframe(monkeypatch):
    """Antes, un día de contexto disparaba 4 llamadas a history_cache.get_history
    (una por timeframe) — con N días evaluados, eran 4*N llamadas, releyendo y
    reconcatenando los mismos Parquet una y otra vez. Ahora debe ser 4 en total,
    sin importar cuántos días se evalúen."""
    dias = _dias_habiles(date(2026, 2, 2), date(2026, 2, 27))
    assert len(dias) > 15  # confirma que estamos probando con varios días, no uno solo

    df_d = _ohlcv(date(2025, 1, 1), 500, 24 * 60)
    df_4h = _ohlcv(date(2026, 1, 1), 300, 240)
    df_15m = _ohlcv(date(2026, 1, 1), 3000, 15)
    df_5m = _ohlcv(date(2026, 1, 1), 9000, 5)
    datos_por_timeframe = {"d": df_d, "4h": df_4h, "15m": df_15m, "5m": df_5m}

    llamadas: list[str] = []

    async def fake_get_history(ticker, timeframe, fecha_inicio, fecha_fin):
        llamadas.append(timeframe)
        return history_cache.filter_range(datos_por_timeframe[timeframe], fecha_inicio, fecha_fin)

    monkeypatch.setattr(runner.history_cache, "get_history", fake_get_history)

    resultados = asyncio.run(runner._evaluar_ticker_para_dias("AAPL", dias, ScanConfig()))

    assert len(llamadas) == 4
    assert set(llamadas) == {"d", "4h", "15m", "5m"}
    assert len(resultados) == len(dias)


def test_evaluar_ticker_para_dias_sin_dias_no_pide_nada(monkeypatch):
    llamado = False

    async def fake_get_history(*args, **kwargs):
        nonlocal llamado
        llamado = True
        return pl.DataFrame()

    monkeypatch.setattr(runner.history_cache, "get_history", fake_get_history)

    resultados = asyncio.run(runner._evaluar_ticker_para_dias("AAPL", [], ScanConfig()))

    assert resultados == []
    assert llamado is False


def test_evaluar_ticker_para_dias_no_pide_intradia_antes_del_piso_conocido(monkeypatch):
    """Días de 2023 (mucho antes de que Schwab tenga intradía real, ver
    history_cache.FECHA_INICIO_DEFAULT) no deben disparar ningún pedido de
    4h/15m/5m — antes de este fix, sí lo hacían (pidiendo un rango que
    Schwab nunca va a tener) y con el token vencido eso rompía todo el
    ticker en vez de simplemente no tener contexto intradía."""
    dias = _dias_habiles(date(2023, 1, 2), date(2023, 1, 13))
    df_d = _ohlcv(date(2021, 1, 1), 800, 24 * 60)

    llamadas: list[str] = []

    async def fake_get_history(ticker, timeframe, fecha_inicio, fecha_fin):
        llamadas.append(timeframe)
        if timeframe == "d":
            return history_cache.filter_range(df_d, fecha_inicio, fecha_fin)
        return pl.DataFrame()

    monkeypatch.setattr(runner.history_cache, "get_history", fake_get_history)

    resultados = asyncio.run(runner._evaluar_ticker_para_dias("AAPL", dias, ScanConfig()))

    assert llamadas == ["d"]  # ningún pedido de 4h/15m/5m
    assert len(resultados) == len(dias)


def test_evaluar_ticker_para_dias_sin_historial_no_rompe(monkeypatch):
    async def fake_get_history(*args, **kwargs):
        raise RuntimeError("sin datos")

    monkeypatch.setattr(runner.history_cache, "get_history", fake_get_history)

    resultados = asyncio.run(
        runner._evaluar_ticker_para_dias("XYZ", [date(2026, 2, 2)], ScanConfig())
    )

    assert resultados == []
