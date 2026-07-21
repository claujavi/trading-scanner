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
