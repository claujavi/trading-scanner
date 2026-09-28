"""
schwab_stream.py — modo SESIÓN (WebSocket streaming) de CLAUDE.md.

`StreamManager` envuelve `schwab.streaming.StreamClient`: suscribe quotes
de nivel 1 (`level_one_equity`, precio/bid/ask/volumen) y velas de 1 minuto
(`chart_equity`), despacha cada mensaje al `MarketDataCache` correspondiente,
y agenda una reevaluación (`asyncio.create_task`, nunca inline) solo cuando
`actualizar_tick`/`actualizar_vela_1m` devuelven que hubo un evento
significativo — nunca en cada tick, para no bloquear `handle_message()`.

Reconexión con backoff exponencial: si el WebSocket se cae, se reintenta
con backoff creciente (nunca se resetea el cache — el evaluador sigue
funcionando con el último estado conocido) y, al reconectar, se
re-suscribe todo lo que el cache tenía en memoria, no solo el set original.

`MockStreamManager` es el mismo API público sin abrir ningún socket real —
genera ticks sintéticos deterministas por ticker (reusa `_seed()` de
mock_schwab.py), para poder desarrollar/testear todo el flujo con
MOCK_SCHWAB=true sin depender de horario de mercado ni token real.
"""

import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Awaitable, Callable, Optional

from ..config import settings
from ..engine.pattern_3bp import EventoPatron3BP
from ..logging_setup import console
from .market_data_cache import MarketDataCache, Vela
from .mock_schwab import _seed
from .schwab_client import get_client

BACKOFF_BASE_S = 2.0
BACKOFF_MAX_S = 60.0
BACKOFF_JITTER = 0.2

OnEventoSignificativo = Callable[[str], Awaitable[None]]
OnEvento3BP = Callable[[str, str, EventoPatron3BP], Awaitable[None]]


class BaseStreamManager(ABC):
    _modo: str = "REAL"

    def __init__(
        self,
        cache: MarketDataCache,
        on_evento: OnEventoSignificativo,
        on_evento_3bp: Optional[OnEvento3BP] = None,
    ):
        self._cache = cache
        self._on_evento = on_evento
        self._on_evento_3bp = on_evento_3bp
        self._conectado = False
        self._ultimo_tick_en: Optional[datetime] = None
        self._intentos_reconexion = 0

    @abstractmethod
    async def start(self, tickers: list[str]) -> None: ...

    @abstractmethod
    async def agregar_tickers(self, tickers: list[str]) -> None: ...

    @abstractmethod
    async def quitar_tickers(self, tickers: list[str]) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    def status(self) -> dict:
        return {
            "conectado": self._conectado,
            "modo": self._modo,
            "tickers_suscritos": self._cache.tickers_suscritos(),
            "ultimo_tick_en": self._ultimo_tick_en.isoformat() if self._ultimo_tick_en else None,
            "intentos_reconexion": self._intentos_reconexion,
        }

    def _despachar_si_evento(self, ticker: str, evento: bool) -> None:
        if evento:
            asyncio.create_task(self._on_evento(ticker))

    def _despachar_eventos_3bp(self) -> None:
        """Drena la cola de eventos ENTRADA de 3BP/4BP acumulados en el
        cache (ver market_data_cache.py::drenar_eventos_3bp) y agenda su
        persistencia — mismo patrón que _despachar_si_evento
        (asyncio.create_task, nunca inline, para no bloquear
        handle_message()). No-op si no se pasó on_evento_3bp al
        construir el manager (opcional — el módulo 3BP puede correr sin
        persistencia en vivo, ej. en tests)."""
        if self._on_evento_3bp is None:
            return
        for ticker, timeframe, evento in self._cache.drenar_eventos_3bp():
            asyncio.create_task(self._on_evento_3bp(ticker, timeframe, evento))


class StreamManager(BaseStreamManager):
    """Conexión real vía schwab.streaming.StreamClient."""

    _modo = "REAL"

    def __init__(
        self,
        cache: MarketDataCache,
        on_evento: OnEventoSignificativo,
        on_evento_3bp: Optional[OnEvento3BP] = None,
    ):
        super().__init__(cache, on_evento, on_evento_3bp)
        self._stream_client = None
        self._task: Optional[asyncio.Task] = None
        self._stop_solicitado = False

    def _crear_stream_client(self):
        import schwab.streaming as streaming

        client = get_client()
        if client is None:
            raise RuntimeError("No hay cliente Schwab autenticado — no se puede iniciar el stream")
        return streaming.StreamClient(client)

    async def _resuscribir_todo(self) -> None:
        tickers = self._cache.tickers_suscritos()
        if not tickers:
            return
        await self._stream_client.level_one_equity_subs(tickers)
        await self._stream_client.chart_equity_subs(tickers)

    def _on_level_one(self, msg: dict) -> None:
        for item in msg.get("content", []):
            ticker = item.get("key")
            if not ticker:
                continue
            precio = item.get("LAST_PRICE", item.get("MARK"))
            if precio is None:
                continue
            self._ultimo_tick_en = datetime.utcnow()
            evento = self._cache.actualizar_tick(
                ticker,
                precio=float(precio),
                bid=item.get("BID_PRICE"),
                ask=item.get("ASK_PRICE"),
                volumen_total=float(item.get("TOTAL_VOLUME", 0.0)),
                timestamp=self._ultimo_tick_en,
            )
            self._despachar_si_evento(ticker, evento)

    def _on_chart_equity(self, msg: dict) -> None:
        for item in msg.get("content", []):
            ticker = item.get("key")
            if not ticker:
                continue
            vela = Vela(
                # utcfromtimestamp, NO fromtimestamp: CHART_TIME_MILLIS es un
                # epoch UTC — fromtimestamp() lo convierte con la hora LOCAL
                # del sistema (ver bug real encontrado 2026-09-28: esta PC
                # corre en horario de Argentina, UTC-3, lo que desplazaba el
                # timestamp guardado 3 horas respecto al instante UTC real que
                # el resto del sistema asume — history_cache/schwab_history
                # sí lo hacen bien, ver CLAUDE.md "timestamps naive pero UTC").
                timestamp=datetime.utcfromtimestamp(item["CHART_TIME_MILLIS"] / 1000),
                open=float(item["OPEN_PRICE"]),
                high=float(item["HIGH_PRICE"]),
                low=float(item["LOW_PRICE"]),
                close=float(item["CLOSE_PRICE"]),
                volume=float(item["VOLUME"]),
            )
            evento = self._cache.actualizar_vela_1m(ticker, vela)
            self._despachar_si_evento(ticker, evento)
            self._despachar_eventos_3bp()

    async def start(self, tickers: list[str]) -> None:
        self._stop_solicitado = False
        self._task = asyncio.create_task(self._run_con_reconexion())

    async def _run_con_reconexion(self) -> None:
        while not self._stop_solicitado:
            try:
                self._stream_client = self._crear_stream_client()
                self._stream_client.add_level_one_equity_handler(self._on_level_one)
                self._stream_client.add_chart_equity_handler(self._on_chart_equity)
                await self._stream_client.login()
                await self._resuscribir_todo()
                self._conectado = True
                self._intentos_reconexion = 0
                console.log(
                    f"[green]Stream iniciado: {len(self._cache.tickers_suscritos())} tickers suscritos[/green]"
                )
                while not self._stop_solicitado:
                    await self._stream_client.handle_message()
            except Exception as exc:
                if self._stop_solicitado:
                    break
                self._conectado = False
                self._intentos_reconexion += 1
                espera = min(BACKOFF_MAX_S, BACKOFF_BASE_S * (2 ** (self._intentos_reconexion - 1)))
                espera += random.uniform(0, espera * BACKOFF_JITTER)
                console.log(
                    f"[yellow]Stream desconectado ({exc}); reintentando en {espera:.1f}s[/yellow]"
                )
                await asyncio.sleep(espera)

    async def agregar_tickers(self, tickers: list[str]) -> None:
        if not tickers or self._stream_client is None or not self._conectado:
            return
        await self._stream_client.level_one_equity_add(tickers)
        await self._stream_client.chart_equity_add(tickers)
        console.log(f"[green]Agregando {len(tickers)} tickers a suscripción existente[/green]")

    async def quitar_tickers(self, tickers: list[str]) -> None:
        eliminados = [t for t in tickers if self._cache.eliminar(t)]
        if not eliminados:
            return
        if self._stream_client is not None and self._conectado:
            try:
                await self._stream_client.level_one_equity_unsubs(eliminados)
                await self._stream_client.chart_equity_unsubs(eliminados)
            except Exception as exc:
                console.log(f"[yellow]No se pudo desuscribir {eliminados} del stream: {exc}[/yellow]")
        console.log(f"[green]Quitados del stream: {eliminados}[/green]")

    async def stop(self) -> None:
        self._stop_solicitado = True
        if self._task:
            self._task.cancel()
        if self._stream_client:
            try:
                await self._stream_client.logout()
            except Exception:
                pass
        self._conectado = False


class MockStreamManager(BaseStreamManager):
    """Genera ticks sintéticos deterministas por ticker, sin abrir socket
    real — mismo API público que StreamManager para poder desarrollar y
    testear el flujo completo con MOCK_SCHWAB=true."""

    _modo = "MOCK"

    def __init__(
        self,
        cache: MarketDataCache,
        on_evento: OnEventoSignificativo,
        intervalo_tick_s: float = 1.0,
        intervalo_vela_s: float = 5.0,
        on_evento_3bp: Optional[OnEvento3BP] = None,
    ):
        super().__init__(cache, on_evento, on_evento_3bp)
        self._intervalo_tick_s = intervalo_tick_s
        self._intervalo_vela_s = intervalo_vela_s
        self._tasks: dict[str, asyncio.Task] = {}

    async def start(self, tickers: list[str]) -> None:
        self._conectado = True
        self._crear_tareas(tickers)
        console.log(f"[green]Stream iniciado (mock): {len(tickers)} tickers suscritos[/green]")

    async def agregar_tickers(self, tickers: list[str]) -> None:
        nuevos = self._crear_tareas(tickers)
        if nuevos:
            console.log(f"[green]Agregando {len(nuevos)} tickers a suscripción existente (mock)[/green]")

    def _crear_tareas(self, tickers: list[str]) -> list[str]:
        nuevos = [t for t in tickers if t not in self._tasks]
        for ticker in nuevos:
            self._tasks[ticker] = asyncio.create_task(self._generar_ticks(ticker))
        return nuevos

    async def quitar_tickers(self, tickers: list[str]) -> None:
        eliminados = []
        for ticker in tickers:
            tarea = self._tasks.pop(ticker, None)
            if tarea is not None:
                tarea.cancel()
            if self._cache.eliminar(ticker):
                eliminados.append(ticker)
        if eliminados:
            console.log(f"[green]Quitados del stream (mock): {eliminados}[/green]")

    async def _generar_ticks(self, ticker: str) -> None:
        cache_ticker = self._cache.get(ticker)
        precio = cache_ticker.ultimo_precio if cache_ticker else 10.0
        volumen = cache_ticker.volumen_acumulado if cache_ticker else 0.0
        minuto_actual = 0
        vela_1m_acumulada: Optional[Vela] = None

        try:
            while True:
                await asyncio.sleep(self._intervalo_tick_s)
                rng = random.Random(_seed(ticker, salt=minuto_actual) ^ id(self))
                precio = max(0.01, precio * (1 + rng.gauss(0.0, 0.003)))
                volumen += rng.randint(100, 5000)
                self._ultimo_tick_en = datetime.utcnow()

                evento = self._cache.actualizar_tick(
                    ticker, precio=precio, bid=precio - 0.01, ask=precio + 0.01,
                    volumen_total=volumen, timestamp=self._ultimo_tick_en,
                )
                self._despachar_si_evento(ticker, evento)

                if vela_1m_acumulada is None:
                    vela_1m_acumulada = Vela(self._ultimo_tick_en, precio, precio, precio, precio, 0.0)
                else:
                    vela_1m_acumulada.high = max(vela_1m_acumulada.high, precio)
                    vela_1m_acumulada.low = min(vela_1m_acumulada.low, precio)
                    vela_1m_acumulada.close = precio
                vela_1m_acumulada.volume += rng.randint(100, 5000)

                minuto_actual += 1
                if minuto_actual % max(1, int(self._intervalo_vela_s / self._intervalo_tick_s)) == 0:
                    evento_vela = self._cache.actualizar_vela_1m(ticker, vela_1m_acumulada)
                    self._despachar_si_evento(ticker, evento_vela)
                    self._despachar_eventos_3bp()
                    vela_1m_acumulada = None
        except asyncio.CancelledError:
            return

    async def stop(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._conectado = False


def crear_stream_manager(
    cache: MarketDataCache,
    on_evento: OnEventoSignificativo,
    on_evento_3bp: Optional[OnEvento3BP] = None,
) -> BaseStreamManager:
    if settings.mock_schwab:
        return MockStreamManager(cache, on_evento, on_evento_3bp=on_evento_3bp)
    return StreamManager(cache, on_evento, on_evento_3bp)
