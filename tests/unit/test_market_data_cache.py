from datetime import datetime

import polars as pl
import pytest

from trading_scanner.fetchers.calendar_client import CalendarWarning
from trading_scanner.fetchers.market_data_cache import MarketDataCache, Vela
from trading_scanner.models import ScanConfig, TickerBasico

_EMPTY_DF = pl.DataFrame(schema={
    "timestamp": pl.Datetime("ms"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
})


def _warning_sin_catalizador() -> CalendarWarning:
    return CalendarWarning(
        nivel="GREEN",
        earnings_24h=False,
        evento_macro_24h=False,
        filing_8k_24h=False,
        upgrade_downgrade_24h=False,
        catalizador_detectado=False,
        disponible=True,
    )


def _ticker_data(precio=10.0, volumen_actual=100_000) -> TickerBasico:
    return TickerBasico(
        ticker="AAPL",
        precio=precio,
        variacion_diaria_pct=3.0,
        volumen_actual=volumen_actual,
        relvol=1.0,
        atr_pct=2.0,
        volumen_promedio=100_000,
    )


def _seed_cache(config: ScanConfig, volumen_promedio=100_000.0) -> MarketDataCache:
    cache = MarketDataCache(config)
    cache.seed(
        ticker_data=_ticker_data(),
        df_5m=_EMPTY_DF,
        df_15m=_EMPTY_DF,
        df_4h=_EMPTY_DF,
        df_d=_EMPTY_DF,
        signals={},
        volumen_promedio=volumen_promedio,
        atr_pct=2.0,
        ivr=40.0,
        warning=_warning_sin_catalizador(),
    )
    return cache


def test_seed_pobla_estado_inicial():
    config = ScanConfig()
    cache = _seed_cache(config)

    assert cache.tiene("AAPL")
    ticker_cache = cache.get("AAPL")
    assert ticker_cache.ultimo_precio == 10.0
    assert ticker_cache.max_dia == 10.0
    assert ticker_cache.min_dia == 10.0


def test_actualizar_tick_detecta_cruce_de_vwap():
    config = ScanConfig()
    cache = _seed_cache(config)
    ts = datetime(2026, 7, 21, 10, 0)

    # primer tick: mismo precio que la siembra -> no hay nuevo max/min ni VWAP previo con qué comparar
    assert cache.actualizar_tick("AAPL", precio=10.0, bid=9.99, ask=10.01,
                                  volumen_total=100_100, timestamp=ts) is False

    ticker_cache = cache.get("AAPL")
    vwap_inicial = ticker_cache.vwap
    assert vwap_inicial is not None

    # tick que cruza por debajo del VWAP ya establecido
    evento = cache.actualizar_tick(
        "AAPL", precio=vwap_inicial - 1.0, bid=None, ask=None,
        volumen_total=100_200, timestamp=ts,
    )
    assert evento is True
    assert cache.get("AAPL").sobre_vwap is False


def test_actualizar_tick_detecta_nuevo_maximo_del_dia():
    config = ScanConfig()
    cache = _seed_cache(config)
    ts = datetime(2026, 7, 21, 10, 0)

    cache.actualizar_tick("AAPL", precio=10.0, bid=None, ask=None,
                           volumen_total=100_000, timestamp=ts)

    evento = cache.actualizar_tick("AAPL", precio=11.0, bid=None, ask=None,
                                    volumen_total=100_000, timestamp=ts)
    assert evento is True
    assert cache.get("AAPL").max_dia == 11.0


def test_actualizar_tick_detecta_cambio_de_categoria_relvol():
    config = ScanConfig()  # relvol_umbral_swing_min=1.5, relvol_umbral_day=3.0
    cache = _seed_cache(config, volumen_promedio=100_000.0)
    ts = datetime(2026, 7, 21, 10, 0)

    # volumen acumulado = 100_000 -> relvol 1.0 -> "BAJO" (ya seedeado)
    assert cache.get("AAPL").relvol_categoria == "BAJO"

    # subir volumen acumulado a 200_000 -> relvol 2.0 -> "SWING"
    evento = cache.actualizar_tick("AAPL", precio=10.0, bid=None, ask=None,
                                    volumen_total=200_000, timestamp=ts)
    assert evento is True
    assert cache.get("AAPL").relvol_categoria == "SWING"

    # un tick que no cambia de categoría no debe marcar evento por relvol
    # (aislamos el chequeo evitando también un nuevo max/min)
    cache.get("AAPL").max_dia = 999.0
    cache.get("AAPL").min_dia = 0.0
    evento2 = cache.actualizar_tick("AAPL", precio=10.0, bid=None, ask=None,
                                     volumen_total=210_000, timestamp=ts)
    assert evento2 is False


def test_actualizar_tick_ticker_no_suscrito_no_rompe():
    cache = MarketDataCache(ScanConfig())
    assert cache.actualizar_tick("MSFT", precio=1.0, bid=None, ask=None,
                                  volumen_total=1, timestamp=datetime.now()) is False


def test_actualizar_vela_1m_bucketea_en_ventanas_de_5m():
    config = ScanConfig()
    cache = _seed_cache(config)

    base = datetime(2026, 7, 21, 9, 30)
    # minutos 30-34 caen todos en la ventana de 5m que arranca en :30
    velas_1m = [
        Vela(base.replace(minute=30), 10.0, 10.2, 9.9, 10.1, 1000),
        Vela(base.replace(minute=31), 10.1, 10.3, 10.0, 10.2, 1000),
        Vela(base.replace(minute=32), 10.2, 10.4, 10.1, 10.3, 1000),
        Vela(base.replace(minute=33), 10.3, 10.5, 10.2, 10.4, 1000),
        Vela(base.replace(minute=34), 10.4, 10.6, 10.3, 10.5, 1000),
    ]
    for v in velas_1m:
        evento = cache.actualizar_vela_1m("AAPL", v)
        assert evento is False  # dentro de la misma ventana de 5m, no cierra

    ticker_cache = cache.get("AAPL")
    assert len(ticker_cache.velas_hoy) == 1
    vela_en_curso = ticker_cache.velas_hoy[0]
    assert vela_en_curso.open == 10.0
    assert vela_en_curso.high == 10.6  # max acumulado de las 5 velas de 1m
    assert vela_en_curso.volume == 5000

    # nueva ventana de 5m (minuto 35) -> cierra la anterior definitivamente
    cache.actualizar_vela_1m("AAPL", Vela(base.replace(minute=35), 10.5, 10.6, 10.4, 10.5, 1000))
    assert len(ticker_cache.velas_hoy) == 2
    vela_cerrada = ticker_cache.velas_hoy[0]
    assert vela_cerrada.high == 10.6
    assert vela_cerrada.volume == 5000
    vela_nueva_parcial = ticker_cache.velas_hoy[1]
    assert vela_nueva_parcial.timestamp == base.replace(minute=35)


def test_snapshot_devuelve_datos_ticker_completos_validos():
    config = ScanConfig()
    cache = _seed_cache(config)

    datos = cache.snapshot("AAPL")
    assert datos is not None
    assert datos.ticker == "AAPL"
    assert datos.precio == 10.0
    assert datos.relvol == pytest.approx(1.0)
    assert datos.warning_calendar == "GREEN"
    assert datos.catalizador_detectado is False


def test_snapshot_ticker_no_suscrito_devuelve_none():
    cache = MarketDataCache(ScanConfig())
    assert cache.snapshot("MSFT") is None


def test_eliminar_saca_ticker_del_cache():
    config = ScanConfig()
    cache = _seed_cache(config)

    assert cache.eliminar("AAPL") is True
    assert cache.tiene("AAPL") is False
    assert cache.snapshot("AAPL") is None
    # eliminar un ticker que no está no debe romper
    assert cache.eliminar("AAPL") is False
