import asyncio
from datetime import date, datetime

import polars as pl

from src.trading_scanner.config import settings
from src.trading_scanner.database import db
from src.trading_scanner.fetchers import history_cache


def _df_para(fecha: date) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [datetime(fecha.year, fecha.month, fecha.day)],
            "open": [10.0],
            "high": [11.0],
            "low": [9.0],
            "close": [10.5],
            "volume": [1000.0],
        }
    )


def _sin_meta(**kwargs):
    async def _noop(**_kwargs):
        return None

    return _noop()


def test_ticker_nuevo_hace_backfill_completo_desde_fecha_default(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    monkeypatch.setattr(db, "upsert_history_cache_meta", lambda **kwargs: _sin_meta(**kwargs))

    llamados = []

    async def fake_get_history_async(ticker, timeframe, n_periods):
        llamados.append(n_periods)
        return _df_para(date.today())

    monkeypatch.setattr(history_cache.schwab_history, "get_history_async", fake_get_history_async)

    asyncio.run(history_cache.actualizar_hasta_hoy("NEWTICKER", "d"))

    assert len(llamados) == 1
    # Backfill completo: el rango pedido cubre desde FECHA_INICIO_DEFAULT
    # hasta hoy, muchísimo más grande que "solo el mes en curso".
    dias_desde_default = (date.today() - history_cache.FECHA_INICIO_DEFAULT["d"]).days
    assert llamados[0] > dias_desde_default / 2

    hoy = date.today()
    archivo = tmp_path / "NEWTICKER" / "d" / str(hoy.year) / f"{hoy.month:02}.parquet"
    assert archivo.exists()


def test_ticker_conocido_solo_refresca_mes_en_curso(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    monkeypatch.setattr(db, "upsert_history_cache_meta", lambda **kwargs: _sin_meta(**kwargs))

    hoy = date.today()
    carpeta_vieja = tmp_path / "AAPL" / "d" / "2024" / "01.parquet"
    carpeta_vieja.parent.mkdir(parents=True, exist_ok=True)
    carpeta_vieja.write_bytes(b"contenido-viejo-no-debe-tocarse")

    llamados = []

    async def fake_get_history_async(ticker, timeframe, n_periods):
        llamados.append(n_periods)
        return _df_para(hoy)

    monkeypatch.setattr(history_cache.schwab_history, "get_history_async", fake_get_history_async)

    asyncio.run(history_cache.actualizar_hasta_hoy("AAPL", "d"))

    assert len(llamados) == 1
    # Ticker ya conocido: solo se pide el mes en curso, un rango chico.
    assert llamados[0] < 40

    archivo_mes_actual = tmp_path / "AAPL" / "d" / str(hoy.year) / f"{hoy.month:02}.parquet"
    assert archivo_mes_actual.exists()
    # El mes viejo no se tocó.
    assert carpeta_vieja.read_bytes() == b"contenido-viejo-no-debe-tocarse"


def test_schwab_sin_datos_no_rompe(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)

    async def fake_get_history_async(ticker, timeframe, n_periods):
        return pl.DataFrame(
            schema={
                "timestamp": pl.Datetime("ms"),
                "open": pl.Float64,
                "high": pl.Float64,
                "low": pl.Float64,
                "close": pl.Float64,
                "volume": pl.Float64,
            }
        )

    monkeypatch.setattr(history_cache.schwab_history, "get_history_async", fake_get_history_async)

    (tmp_path / "AAPL" / "d").mkdir(parents=True)

    asyncio.run(history_cache.actualizar_hasta_hoy("AAPL", "d"))  # no debe lanzar
