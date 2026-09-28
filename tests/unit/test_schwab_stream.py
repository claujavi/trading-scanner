import asyncio
from datetime import datetime

from trading_scanner.fetchers.calendar_client import CalendarWarning
from trading_scanner.fetchers.market_data_cache import MarketDataCache
from trading_scanner.fetchers.schwab_stream import BACKOFF_MAX_S, MockStreamManager, StreamManager
from trading_scanner.models import ScanConfig, TickerBasico

import polars as pl

_EMPTY_DF = pl.DataFrame(schema={
    "timestamp": pl.Datetime("ms"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
})


def _warning() -> CalendarWarning:
    return CalendarWarning(
        nivel="GREEN", earnings_24h=False, evento_macro_24h=False,
        filing_8k_24h=False, upgrade_downgrade_24h=False,
        catalizador_detectado=False, disponible=True,
    )


def _cache_con_ticker(ticker: str = "AAPL") -> MarketDataCache:
    cache = MarketDataCache(ScanConfig())
    cache.seed(
        ticker_data=TickerBasico(
            ticker=ticker, precio=10.0, variacion_diaria_pct=3.0,
            volumen_actual=100_000, relvol=1.0, atr_pct=2.0, volumen_promedio=100_000,
        ),
        df_5m=_EMPTY_DF, df_15m=_EMPTY_DF, df_4h=_EMPTY_DF, df_d=_EMPTY_DF,
        signals={}, volumen_promedio=100_000.0, atr_pct=2.0, ivr=40.0,
        warning=_warning(),
    )
    return cache


def test_despachar_si_evento_agenda_tarea_solo_si_evento():
    async def body():
        llamados = []

        async def on_evento(ticker: str):
            llamados.append(ticker)

        cache = _cache_con_ticker()
        mgr = MockStreamManager(cache, on_evento)

        mgr._despachar_si_evento("AAPL", False)
        mgr._despachar_si_evento("AAPL", True)
        await asyncio.sleep(0)  # deja correr la tarea agendada con create_task

        assert llamados == ["AAPL"]

    asyncio.run(body())


def test_mock_start_y_agregar_tickers_no_duplica_tareas():
    async def body():
        async def on_evento(ticker: str):
            pass

        cache = _cache_con_ticker("AAPL")
        cache.seed(
            ticker_data=TickerBasico(
                ticker="MSFT", precio=20.0, variacion_diaria_pct=1.0,
                volumen_actual=50_000, relvol=1.0, atr_pct=1.5, volumen_promedio=50_000,
            ),
            df_5m=_EMPTY_DF, df_15m=_EMPTY_DF, df_4h=_EMPTY_DF, df_d=_EMPTY_DF,
            signals={}, volumen_promedio=50_000.0, atr_pct=1.5, ivr=30.0,
            warning=_warning(),
        )

        mgr = MockStreamManager(cache, on_evento, intervalo_tick_s=100.0)
        await mgr.start(["AAPL"])
        tarea_aapl_original = mgr._tasks["AAPL"]

        # agregar_tickers con un ticker repetido + uno nuevo: no debe tocar la tarea existente
        await mgr.agregar_tickers(["AAPL", "MSFT"])

        assert set(mgr._tasks.keys()) == {"AAPL", "MSFT"}
        assert mgr._tasks["AAPL"] is tarea_aapl_original  # no se reinició

        await mgr.stop()
        assert mgr._tasks == {}

    asyncio.run(body())


def test_mock_status_refleja_cache():
    async def body():
        async def on_evento(ticker: str):
            pass

        cache = _cache_con_ticker()
        mgr = MockStreamManager(cache, on_evento, intervalo_tick_s=100.0)
        await mgr.start(["AAPL"])

        status = mgr.status()
        assert status["conectado"] is True
        assert status["modo"] == "MOCK"
        assert status["tickers_suscritos"] == ["AAPL"]

        await mgr.stop()
        assert mgr.status()["conectado"] is False

    asyncio.run(body())


def test_mock_quitar_tickers_saca_del_cache_y_cancela_tarea():
    async def body():
        async def on_evento(ticker: str):
            pass

        cache = _cache_con_ticker("AAPL")
        mgr = MockStreamManager(cache, on_evento, intervalo_tick_s=100.0)
        await mgr.start(["AAPL"])
        assert cache.tiene("AAPL")

        await mgr.quitar_tickers(["AAPL"])

        assert "AAPL" not in mgr._tasks
        assert not cache.tiene("AAPL")
        assert mgr.status()["tickers_suscritos"] == []

    asyncio.run(body())


def test_stream_manager_backoff_reintenta_con_espera_creciente():
    async def body():
        async def on_evento(ticker: str):
            pass

        esperas_registradas = []

        async def sleep_falso(segundos):
            esperas_registradas.append(segundos)
            if len(esperas_registradas) >= 3:
                mgr._stop_solicitado = True
                raise asyncio.CancelledError()

        cache = _cache_con_ticker()
        mgr = StreamManager(cache, on_evento)

        class _ClienteFalso:
            async def login(self):
                raise ConnectionError("simulado")

            async def logout(self):
                pass

            def add_level_one_equity_handler(self, handler):
                pass

            def add_chart_equity_handler(self, handler):
                pass

        mgr._crear_stream_client = lambda: _ClienteFalso()

        orig_sleep = asyncio.sleep
        asyncio.sleep = sleep_falso
        try:
            await mgr._run_con_reconexion()
        except asyncio.CancelledError:
            pass
        finally:
            asyncio.sleep = orig_sleep

        assert len(esperas_registradas) >= 2
        # backoff creciente (con jitter, pero estrictamente no decreciente en la base)
        assert esperas_registradas[1] >= esperas_registradas[0] * 0.9
        assert all(e <= BACKOFF_MAX_S * 1.2 for e in esperas_registradas)
        assert mgr._intentos_reconexion >= 2

    asyncio.run(body())


def test_stream_manager_agregar_tickers_sin_conexion_no_rompe():
    async def body():
        async def on_evento(ticker: str):
            pass

        cache = _cache_con_ticker()
        mgr = StreamManager(cache, on_evento)
        await mgr.agregar_tickers(["AAPL"])  # sin conexión activa: no debe lanzar

    asyncio.run(body())


def test_stream_manager_real_acepta_on_evento_3bp():
    """Regresión: StreamManager (el real) tiene su propio __init__ que
    sobreescribe el de BaseStreamManager — agregar un parámetro nuevo ahí
    y no acá pasa desapercibido en los tests (que solo instancian
    MockStreamManager) pero rompe crear_stream_manager() en producción con
    credenciales reales (modo REAL), con un TypeError silencioso detrás
    del pipeline lento. Ver bug real encontrado 2026-08-04: el stream
    nunca conectaba porque StreamManager(cache, on_evento, on_evento_3bp)
    fallaba con 'takes 3 positional arguments but 4 were given'."""
    async def on_evento(ticker: str):
        pass

    async def on_evento_3bp(ticker: str, timeframe: str, evento):
        pass

    cache = _cache_con_ticker()
    mgr = StreamManager(cache, on_evento, on_evento_3bp)
    assert mgr._on_evento_3bp is on_evento_3bp


# ── _despachar_eventos_3bp — cola de eventos ENTRADA del módulo 3BP/4BP ────


def test_despachar_eventos_3bp_agenda_una_tarea_por_evento_y_vacia_la_cola():
    async def body():
        from trading_scanner.engine.pattern_3bp import Estado3BP, EventoPatron3BP

        llamados = []

        async def on_evento(ticker: str):
            pass

        async def on_evento_3bp(ticker: str, timeframe: str, evento):
            llamados.append((ticker, timeframe, evento))

        cache = _cache_con_ticker("AAPL")
        evento1 = EventoPatron3BP(estado=Estado3BP.ENTRADA, timestamp=datetime(2026, 1, 2, 9, 35), tipo="3BP", entry=10.0, stop=9.0, tier="confirmado")
        evento2 = EventoPatron3BP(estado=Estado3BP.ENTRADA, timestamp=datetime(2026, 1, 2, 9, 50), tipo="4BP", entry=20.0, stop=19.0, tier="sin_confirmar")
        cache._eventos_3bp_pendientes = [("AAPL", "5m", evento1), ("AAPL", "15m", evento2)]

        mgr = MockStreamManager(cache, on_evento, on_evento_3bp=on_evento_3bp)
        mgr._despachar_eventos_3bp()

        assert cache._eventos_3bp_pendientes == []  # drenada
        await asyncio.sleep(0)  # deja correr las tareas agendadas con create_task

        assert len(llamados) == 2
        assert llamados[0][:2] == ("AAPL", "5m")
        assert llamados[1][:2] == ("AAPL", "15m")

    asyncio.run(body())


def test_despachar_eventos_3bp_es_no_op_sin_callback():
    async def body():
        from trading_scanner.engine.pattern_3bp import Estado3BP, EventoPatron3BP

        async def on_evento(ticker: str):
            pass

        cache = _cache_con_ticker("AAPL")
        evento = EventoPatron3BP(estado=Estado3BP.ENTRADA, timestamp=datetime(2026, 1, 2, 9, 35), tipo="3BP", entry=10.0, stop=9.0, tier="confirmado")
        cache._eventos_3bp_pendientes = [("AAPL", "5m", evento)]

        mgr = MockStreamManager(cache, on_evento)  # on_evento_3bp=None (default)
        mgr._despachar_eventos_3bp()

        # sin callback, no se drena — no hay a quién avisar
        assert cache._eventos_3bp_pendientes == [("AAPL", "5m", evento)]

    asyncio.run(body())


# ── _on_chart_equity: timestamp debe ser UTC, no hora local del sistema ────


def test_on_chart_equity_convierte_epoch_a_utc_no_hora_local():
    """Bug real encontrado 2026-09-28: datetime.fromtimestamp() usaba la hora
    LOCAL del sistema (esta PC corre en Argentina, UTC-3) para un epoch que
    Schwab manda en UTC — desplazaba el timestamp guardado ~3 horas respecto
    al instante real. El resto del sistema (schwab_history.py, docs/CLAUDE.md)
    asume "naive pero UTC" en todos lados; este test verifica el mismo
    contrato acá, independientemente de en qué huso horario corra la máquina
    que ejecuta el test."""
    cache = _cache_con_ticker("AAPL")
    velas_recibidas = []
    cache.actualizar_vela_1m = lambda ticker, vela_1m: velas_recibidas.append(vela_1m) or False

    manager = StreamManager(cache, on_evento=lambda t: None)
    # 2026-09-23 13:31:00 UTC, en milisegundos — instante fijo, no depende del reloj local
    epoch_ms = 1790170260000
    manager._on_chart_equity({
        "content": [{
            "key": "AAPL", "CHART_TIME_MILLIS": epoch_ms,
            "OPEN_PRICE": 10.0, "HIGH_PRICE": 10.5, "LOW_PRICE": 9.8, "CLOSE_PRICE": 10.2,
            "VOLUME": 1000.0,
        }]
    })

    assert len(velas_recibidas) == 1
    assert velas_recibidas[0].timestamp == datetime(2026, 9, 23, 13, 31, 0)
