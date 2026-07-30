import asyncio
from datetime import date, datetime, timedelta

import polars as pl

from src.trading_scanner.config import settings
from src.trading_scanner.database import db
from src.trading_scanner.fetchers import history_cache


def _sin_meta(**kwargs):
    async def _noop(**_kwargs):
        return None

    return _noop()


def _df_desde(fecha_inicio: date, n_meses: int) -> pl.DataFrame:
    """Simula lo que Schwab devuelve para un ticker con historial real
    limitado: una vela por mes, arrancando en fecha_inicio (el listado real
    del ticker), nunca antes — como pasa con instrumentos recién listados."""
    fechas = []
    year, month = fecha_inicio.year, fecha_inicio.month
    for _ in range(n_meses):
        fechas.append(datetime(year, month, 15))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return pl.DataFrame(
        {
            "timestamp": fechas,
            "open": [10.0] * n_meses,
            "high": [11.0] * n_meses,
            "low": [9.0] * n_meses,
            "close": [10.5] * n_meses,
            "volume": [1000] * n_meses,
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("ms")))


def test_ticker_con_historial_limitado_marca_meses_previos_como_vacios(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    monkeypatch.setattr(db, "upsert_history_cache_meta", lambda **kwargs: _sin_meta(**kwargs))

    listado_real = date(2025, 12, 1)
    llamados = []

    async def fake_get_history_async(ticker, timeframe, n_periods):
        llamados.append(n_periods)
        return _df_desde(listado_real, 3)  # dic-2025, ene-2026, feb-2026

    monkeypatch.setattr(history_cache.schwab_history, "get_history_async", fake_get_history_async)

    resultado = asyncio.run(
        history_cache.get_history("NUEVOTICKER", "d", date(2021, 1, 1), date(2026, 2, 28))
    )

    assert len(llamados) == 1
    assert resultado.height == 3  # solo las 3 velas reales, nada inventado

    # Los meses previos al listado real quedaron marcados (Parquet vacío) —
    # no "faltantes" — para no volver a pedirlos.
    archivo_viejo = tmp_path / "NUEVOTICKER" / "d" / "2024" / "06.parquet"
    assert archivo_viejo.exists()
    assert pl.read_parquet(archivo_viejo).height == 0


def test_segundo_pedido_del_mismo_rango_viejo_no_vuelve_a_golpear_schwab(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    monkeypatch.setattr(db, "upsert_history_cache_meta", lambda **kwargs: _sin_meta(**kwargs))

    llamados = []

    async def fake_get_history_async(ticker, timeframe, n_periods):
        llamados.append(n_periods)
        return _df_desde(date(2025, 12, 1), 3)

    monkeypatch.setattr(history_cache.schwab_history, "get_history_async", fake_get_history_async)

    asyncio.run(history_cache.get_history("NUEVOTICKER", "d", date(2021, 1, 1), date(2026, 2, 28)))
    assert len(llamados) == 1

    # Mismo pedido de nuevo (como pasaría en cada trial del optimizador) —
    # no debe tocar la red esta vez.
    resultado = asyncio.run(
        history_cache.get_history("NUEVOTICKER", "d", date(2021, 1, 1), date(2026, 2, 28))
    )
    assert len(llamados) == 1  # sigue en 1, no se repitió
    assert resultado.height == 3


def test_hueco_en_medio_del_rango_tambien_se_marca(tmp_path, monkeypatch):
    """Un ticker ilíquido puede tener meses sin ninguna vela en medio de un
    rango con datos antes y después (no solo 'antes del listado') — ej.
    GV/KPELF/NWWCF/RSNHF en producción. Ese hueco también debe marcarse."""
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    monkeypatch.setattr(db, "upsert_history_cache_meta", lambda **kwargs: _sin_meta(**kwargs))

    # Datos en enero y marzo de 2022, pero NADA en febrero (mes sin operaciones).
    df_con_hueco = pl.DataFrame(
        {
            "timestamp": [datetime(2022, 1, 15), datetime(2022, 3, 15)],
            "open": [10.0, 10.0],
            "high": [11.0, 11.0],
            "low": [9.0, 9.0],
            "close": [10.5, 10.5],
            "volume": [1000, 1000],
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("ms")))

    llamados = []

    async def fake_get_history_async(ticker, timeframe, n_periods):
        llamados.append(n_periods)
        return df_con_hueco

    monkeypatch.setattr(history_cache.schwab_history, "get_history_async", fake_get_history_async)

    asyncio.run(history_cache.get_history("ILIQUIDO", "d", date(2022, 1, 1), date(2022, 3, 31)))

    archivo_hueco = tmp_path / "ILIQUIDO" / "d" / "2022" / "02.parquet"
    assert archivo_hueco.exists()
    assert pl.read_parquet(archivo_hueco).height == 0

    # Pedir el mismo rango de nuevo no debe volver a golpear Schwab.
    asyncio.run(history_cache.get_history("ILIQUIDO", "d", date(2022, 1, 1), date(2022, 3, 31)))
    assert len(llamados) == 1


def test_mes_en_curso_nunca_se_marca_vacio(tmp_path, monkeypatch):
    """El mes en curso no debe marcarse como vacío aunque falte en la
    respuesta — puede tener datos parciales todavía; lo mantiene al día
    actualizar_hasta_hoy() en cada scan, no este mecanismo."""
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    monkeypatch.setattr(db, "upsert_history_cache_meta", lambda **kwargs: _sin_meta(**kwargs))

    hoy = date.today()
    mes_pasado = date(hoy.year, hoy.month, 1) - timedelta(days=32)

    async def fake_get_history_async(ticker, timeframe, n_periods):
        return _df_desde(date(mes_pasado.year, mes_pasado.month, 1), 1)

    monkeypatch.setattr(history_cache.schwab_history, "get_history_async", fake_get_history_async)

    asyncio.run(history_cache.get_history("SINMESACTUAL", "d", mes_pasado, hoy))

    archivo_mes_actual = tmp_path / "SINMESACTUAL" / "d" / str(hoy.year) / f"{hoy.month:02}.parquet"
    assert not archivo_mes_actual.exists()


def test_ticker_con_historial_profundo_no_marca_nada_de_mas(tmp_path, monkeypatch):
    """Si Schwab devuelve datos que ya cubren todo el fecha_inicio pedido
    (ticker con historial profundo), no debe marcarse ningún mes vacío."""
    monkeypatch.setattr(settings, "backtest_data_path", tmp_path)
    monkeypatch.setattr(db, "upsert_history_cache_meta", lambda **kwargs: _sin_meta(**kwargs))

    async def fake_get_history_async(ticker, timeframe, n_periods):
        return _df_desde(date(2020, 1, 1), 3)

    monkeypatch.setattr(history_cache.schwab_history, "get_history_async", fake_get_history_async)

    asyncio.run(history_cache.get_history("VIEJOTICKER", "d", date(2020, 1, 1), date(2020, 3, 31)))

    # No debería existir ningún parquet vacío marcado antes de 2020-01.
    archivo_previo = tmp_path / "VIEJOTICKER" / "d" / "2019" / "12.parquet"
    assert not archivo_previo.exists()
