"""Wireo en vivo del módulo 3BP/4BP dentro de MarketDataCache — paso 3 de
docs/spec_modulo_3bp_4bp.md."""

from datetime import datetime

import polars as pl

from src.trading_scanner.engine.pattern_3bp import Estado3BP
from src.trading_scanner.fetchers.calendar_client import CalendarWarning
from src.trading_scanner.fetchers.market_data_cache import MarketDataCache, Vela
from src.trading_scanner.models import ResultadoBp34, ScanConfig, TickerBasico

_EMPTY_DF = pl.DataFrame(schema={
    "timestamp": pl.Datetime("ms"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
})

_BASE = datetime(2026, 7, 31, 9, 30)


def _warning_sin_catalizador() -> CalendarWarning:
    return CalendarWarning(
        nivel="GREEN", earnings_24h=False, evento_macro_24h=False, filing_8k_24h=False,
        upgrade_downgrade_24h=False, catalizador_detectado=False, disponible=True,
    )


def _ticker_data() -> TickerBasico:
    return TickerBasico(
        ticker="AAPL", precio=100.0, variacion_diaria_pct=3.0, volumen_actual=100_000,
        relvol=1.0, atr_pct=2.0, volumen_promedio=100_000,
    )


def _seed_cache(config: ScanConfig, df_5m: pl.DataFrame = _EMPTY_DF, df_15m: pl.DataFrame = _EMPTY_DF) -> MarketDataCache:
    cache = MarketDataCache(config)
    cache.seed(
        ticker_data=_ticker_data(),
        df_5m=df_5m,
        df_15m=df_15m,
        df_4h=_EMPTY_DF,
        df_d=_EMPTY_DF,
        signals={},
        volumen_promedio=100_000.0,
        atr_pct=2.0,
        ivr=40.0,
        warning=_warning_sin_catalizador(),
    )
    return cache


def _tick(minuto: int, open_, high, low, close, volume=1000):
    return Vela(_BASE.replace(minute=minuto) if minuto < 60 else _BASE.replace(hour=10, minute=minuto - 60),
                open_, high, low, close, volume)


# ── Series propias, sin heredar contexto histórico ──────────────────────────


def test_velas_3bp_arrancan_vacias_aunque_se_siembre_con_historial():
    """A diferencia de velas_hoy (sembrada con df_5m), las series de 3BP
    empiezan vacías — el patrón solo considera velas de la sesión de hoy."""
    df_5m_con_historial = pl.DataFrame({
        "timestamp": [datetime(2026, 7, 30, 9, 30)],
        "open": [50.0], "high": [50.5], "low": [49.5], "close": [50.0], "volume": [1000.0],
    })
    config = ScanConfig()
    cache = _seed_cache(config, df_5m=df_5m_con_historial)

    ticker_cache = cache.get("AAPL")
    assert len(ticker_cache.velas_hoy) == 1  # sí heredó el historial
    assert ticker_cache.velas_3bp_5m == []   # 3BP no
    assert ticker_cache.velas_3bp_15m == []


def test_detectores_3bp_se_instancian_con_los_parametros_de_config():
    config = ScanConfig(bp34_wrb_multiplicador_5m=3.5, bp34_wrb_multiplicador_15m=1.5)
    cache = _seed_cache(config)

    ticker_cache = cache.get("AAPL")
    assert ticker_cache.detector_3bp_5m.wrb_multiplicador == 3.5
    assert ticker_cache.detector_3bp_15m.wrb_multiplicador == 1.5


# ── Bucketeo de 5m y 15m en paralelo, independiente entre sí ────────────────


def test_bucketeo_5m_y_15m_corren_en_paralelo_sin_interferirse():
    config = ScanConfig()
    cache = _seed_cache(config)

    # 20 ticks de 1m (minutos 30-49).
    for m in range(30, 50):
        cache.actualizar_vela_1m("AAPL", _tick(m, 100.0, 100.2, 99.8, 100.0))

    ticker_cache = cache.get("AAPL")
    # 5m: ventanas [30-34],[35-39],[40-44] cerradas + [45-49] en curso -> 4.
    assert len(ticker_cache.velas_3bp_5m) == 4
    # 15m: ventana [30-44] cerrada + [45-59] en curso -> 2.
    assert len(ticker_cache.velas_3bp_15m) == 2


# ── Detección de patrón real a través del wireo completo ────────────────────


def test_wireo_detecta_barra1_wrb_en_vivo_sobre_5m():
    """3 velas de 5m: dos tranquilas (contexto de ATR) + una WRB. El
    detector recién se llama a partir de que hay >= 2 velas cerradas de
    contexto para ATR14 (ver _atr14_de_velas) — la 3ra vela (WRB) dispara
    la transición a POSIBLE."""
    config = ScanConfig()
    cache = _seed_cache(config)

    minuto = 30
    # Vela 1 (quieta, 30-34)
    for _ in range(5):
        cache.actualizar_vela_1m("AAPL", _tick(minuto, 100.0, 100.1, 99.9, 100.0))
        minuto += 1
    # Vela 2 (quieta, 35-39)
    for _ in range(5):
        cache.actualizar_vela_1m("AAPL", _tick(minuto, 100.0, 100.1, 99.9, 100.0))
        minuto += 1
    # Vela 3 (WRB, 40-44) — rango grande desde el primer tick de la ventana
    cache.actualizar_vela_1m("AAPL", _tick(minuto, 100.0, 115.0, 90.0, 110.0))
    minuto += 1
    for _ in range(4):
        cache.actualizar_vela_1m("AAPL", _tick(minuto, 110.0, 111.0, 109.0, 110.0))
        minuto += 1

    ticker_cache = cache.get("AAPL")
    assert ticker_cache.ultimo_evento_3bp_5m is None  # todavía no cerró la vela 3

    # Un tick de la ventana siguiente (45) cierra la vela 3 (WRB) y dispara la evaluación.
    cache.actualizar_vela_1m("AAPL", _tick(minuto, 110.0, 110.2, 109.8, 110.0))

    assert ticker_cache.ultimo_evento_3bp_5m is not None
    assert ticker_cache.ultimo_evento_3bp_5m.estado == Estado3BP.POSIBLE
    assert ticker_cache.detector_3bp_5m.estado == Estado3BP.POSIBLE
    assert cache.drenar_eventos_3bp() == []  # POSIBLE no encola — solo ENTRADA


# ── Cola de eventos ENTRADA (persistencia en vivo, ver main.py::_on_evento_3bp) ──


def test_drenar_eventos_3bp_devuelve_y_vacia_la_cola():
    from src.trading_scanner.engine.pattern_3bp import EventoPatron3BP

    config = ScanConfig()
    cache = _seed_cache(config)
    evento = EventoPatron3BP(estado=Estado3BP.ENTRADA, timestamp=_BASE, tipo="3BP", entry=10.0, stop=9.0, tier="confirmado")
    vela = Vela(_BASE, 10.0, 10.2, 9.8, 10.0, 1000.0)
    cache._eventos_3bp_pendientes = [("AAPL", "5m", evento, vela)]

    drenados = cache.drenar_eventos_3bp()

    assert drenados == [("AAPL", "5m", evento, vela)]
    assert cache.drenar_eventos_3bp() == []  # ya vacía


def test_procesar_3bp_encola_solo_en_entrada_no_en_otros_estados():
    """Aísla la lógica nueva (encolar en ENTRADA) del cálculo del patrón en
    sí (ya cubierto en tests/unit/test_pattern_3bp.py) — se reemplaza
    procesar_barra por un doble canneado para cada estado posible."""
    from src.trading_scanner.engine.pattern_3bp import EventoPatron3BP

    for estado, debe_encolar in (
        (Estado3BP.POSIBLE, False),
        (Estado3BP.ESPERANDO_ENTRADA, False),
        (Estado3BP.SIN_PATRON, False),
        (Estado3BP.ENTRADA, True),
    ):
        config = ScanConfig()
        cache = _seed_cache(config)
        ticker_cache = cache.get("AAPL")
        evento_cann = EventoPatron3BP(estado=estado, timestamp=_BASE, tipo="3BP", entry=10.0, stop=9.0, tier="confirmado")
        ticker_cache.detector_3bp_5m.procesar_barra = lambda *a, **k: evento_cann

        # 3 ticks en ventanas distintas: la 1ra vela cerrada (30-34) es puro
        # contexto — _atr14_de_velas exige >= 2 velas cerradas, así que
        # procesar_barra recién se llama al cerrar la 2da (35-39), con la
        # 1ra ya en el contexto (mismo umbral que en vivo/el walker).
        cache.actualizar_vela_1m("AAPL", _tick(30, 100.0, 100.1, 99.9, 100.0))
        cache.actualizar_vela_1m("AAPL", _tick(35, 100.0, 100.1, 99.9, 100.0))
        cache.actualizar_vela_1m("AAPL", _tick(40, 100.0, 100.1, 99.9, 100.0))

        pendientes = cache.drenar_eventos_3bp()
        if debe_encolar:
            assert len(pendientes) == 1 and pendientes[0][2] is evento_cann, estado
        else:
            assert pendientes == [], estado


# ── Seguimiento de posiciones 3BP/4BP ya abiertas ─────────────────────────
# Wireo (MarketDataCache._resolver_posiciones_abiertas/agregar_posicion_3bp_abierta/
# drenar_resoluciones_3bp) — la lógica de resolución en sí (target/stop/cierre
# forzado) ya está cubierta en test_pattern_3bp.py::SeguidorPosicion3BP. Acá
# se usa un doble simple en vez de un SeguidorPosicion3BP real, para aislar
# el wireo de esa lógica.


class _SeguidorFalso:
    def __init__(self, timeframe: str, resultado=None):
        self.timeframe = timeframe
        self._resultado = resultado
        self.velas_vistas = []

    def procesar_vela(self, vela):
        self.velas_vistas.append(vela)
        return self._resultado


def test_agregar_posicion_3bp_abierta_engancha_al_ticker_existente():
    cache = _seed_cache(ScanConfig())
    seguidor = _SeguidorFalso("5m")

    assert cache.agregar_posicion_3bp_abierta("AAPL", 123, seguidor) is True
    assert cache.get("AAPL").posiciones_3bp_abiertas == [(123, seguidor)]


def test_agregar_posicion_3bp_abierta_false_si_el_ticker_no_esta_en_el_cache():
    cache = _seed_cache(ScanConfig())
    assert cache.agregar_posicion_3bp_abierta("MSFT", 1, _SeguidorFalso("5m")) is False


def test_resolver_posiciones_abiertas_ignora_timeframe_distinto():
    cache = _seed_cache(ScanConfig())
    seguidor_15m = _SeguidorFalso("15m")
    cache.agregar_posicion_3bp_abierta("AAPL", 1, seguidor_15m)

    cache._resolver_posiciones_abiertas(cache.get("AAPL"), "5m", _tick(30, 10.0, 10.2, 9.8, 10.0))

    assert seguidor_15m.velas_vistas == []  # no se tocó — es de otro timeframe
    assert cache.get("AAPL").posiciones_3bp_abiertas == [(1, seguidor_15m)]


def test_resolver_posiciones_abiertas_deja_abierta_si_no_resuelve():
    cache = _seed_cache(ScanConfig())
    seguidor = _SeguidorFalso("5m", resultado=None)
    cache.agregar_posicion_3bp_abierta("AAPL", 1, seguidor)

    vela = _tick(30, 10.0, 10.2, 9.8, 10.0)
    cache._resolver_posiciones_abiertas(cache.get("AAPL"), "5m", vela)

    assert seguidor.velas_vistas == [vela]
    assert cache.get("AAPL").posiciones_3bp_abiertas == [(1, seguidor)]
    assert cache.drenar_resoluciones_3bp() == []


def test_resolver_posiciones_abiertas_encola_resolucion_y_saca_de_la_lista():
    resultado = (ResultadoBp34.TARGET, 2.0, 2.5, -0.3, 15)
    cache = _seed_cache(ScanConfig())
    seguidor = _SeguidorFalso("5m", resultado=resultado)
    cache.agregar_posicion_3bp_abierta("AAPL", 42, seguidor)

    cache._resolver_posiciones_abiertas(cache.get("AAPL"), "5m", _tick(30, 10.0, 10.2, 9.8, 10.0))

    assert cache.get("AAPL").posiciones_3bp_abiertas == []  # ya se resolvió, sale de la lista
    assert cache.drenar_resoluciones_3bp() == [(42, "AAPL", "5m", *resultado)]
    assert cache.drenar_resoluciones_3bp() == []  # ya drenada
