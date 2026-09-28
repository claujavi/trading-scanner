"""
FastAPI application principal — Trading Scanner.

Lifespan:
  - Startup: inicializa Turso, monta static/templates, arranca CSV watcher
  - Shutdown: detiene watcher

Rutas:
  GET /           → dashboard HTML
  GET /scan/*     → api/scan.py
  GET /settings   → api/settings.py
  GET /health     → health check JSON
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .api.backtest import router as backtest_router
from .api.config import router as config_router
from .api.optimize import router as optimize_router
from .api.patrones_3bp import router as patrones_3bp_router
from .api.scan import _dedupe_latest_por_ticker
from .api.scan import router as scan_router
from .api.schwab import router as schwab_router
from .api.settings import router as settings_router
from .api.stream import router as stream_router
from .api.ticker import router as ticker_router
from .backtest.walker_3bp import _df_a_velas, evento_en_ventana_permitida
from .config import settings
from .database import db
from .engine.pattern_3bp import SeguidorPosicion3BP, fecha_ny
from .fetchers import history_cache
from .fetchers.market_data_cache import MarketDataCache
from .fetchers.schwab_client import estado_conexion
from .fetchers.schwab_stream import crear_stream_manager
from .ingest.csv_parser import parse_csv
from .ingest.csv_watcher import CSVWatcher
from .logging_setup import console
from .models import Bp34Evento, FuenteDatos

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"
_STATIC_DIR = _PROJECT_ROOT / "static"

_NY_TZ = ZoneInfo("America/New_York")


def _to_ny(value: datetime, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """Los timestamps se guardan naive en UTC (datetime.utcnow()) — se
    muestran en hora de Nueva York porque es la referencia horaria que ya
    usa el resto del sistema (horario hábil, feriados NYSE) en vez de UTC
    crudo o la hora local del trader."""
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(_NY_TZ).strftime(fmt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Turso ──────────────────────────────────────────────────────────────
    try:
        await db.initialize_schema()
        console.log("[green]Schema Turso inicializado[/green]")
    except Exception as exc:
        console.log(f"[yellow]Turso no disponible: {exc} — continuando sin persistencia[/yellow]")

    # ── Templates y static ────────────────────────────────────────────────
    _TEMPLATES_DIR.mkdir(exist_ok=True)
    _STATIC_DIR.mkdir(exist_ok=True)

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    templates.env.filters["to_ny"] = _to_ny
    app.state.templates = templates
    app.state.settings = settings
    app.state.latest_results = []

    # ── Streaming de sesión (Sprint 2) ──────────────────────────────────────
    # market_cache vive en memoria durante toda la vida del proceso; se
    # siembra por process_ticker() en cada corrida del pipeline pre-market
    # (ver pipeline.py). stream_manager arranca recién con el primer CSV
    # del día — no tiene sentido abrir el WebSocket sin ningún ticker.
    from .pipeline import get_active_config

    config_inicial = await get_active_config()
    app.state.market_cache = MarketDataCache(config_inicial)
    app.state.stream_manager = None

    async def _on_evento_significativo(ticker: str):
        cache_ticker = app.state.market_cache.get(ticker)
        if cache_ticker is None or cache_ticker.lock.locked():
            return
        async with cache_ticker.lock:
            datos = app.state.market_cache.snapshot(ticker)
            if datos is None:
                return
            config = await get_active_config()

            from .engine.evaluator import evaluar
            result = evaluar(datos, config)

            delta_day = abs(result.score_day - cache_ticker.ultimo_score_day)
            delta_swing = abs(result.score_swing - cache_ticker.ultimo_score_swing)
            if delta_day > 0.15 or delta_swing > 0.15:
                try:
                    await db.insert_scan_result(result)
                    console.log(
                        f"[cyan]Stream: {ticker} reevaluado (delta_day={delta_day:.2f} "
                        f"delta_swing={delta_swing:.2f}) -> {result.clasificacion}[/cyan]"
                    )
                except Exception as exc:
                    console.log(f"[red]Error persistiendo reevaluación de {ticker}: {exc}[/red]")
                cache_ticker.ultimo_score_day = result.score_day
                cache_ticker.ultimo_score_swing = result.score_swing
                cache_ticker.ultima_clasificacion = result.clasificacion
            cache_ticker.ultima_evaluacion = datetime.utcnow()

    async def _on_evento_3bp(ticker: str, timeframe: str, evento, vela) -> None:
        """Persiste un evento ENTRADA del módulo 3BP/4BP en vivo y engancha
        su seguimiento (SeguidorPosicion3BP) para resolver target/stop/cierre
        forzado a medida que lleguen las próximas velas — cierra el gap
        documentado en docs/spec_modulo_3bp_4bp.md sección 6 (modo shadow):
        antes de esto la entrada quedaba ABIERTO para siempre, sin que nada
        siguiera el precio real post-señal (a diferencia del backtest,
        walker_3bp.py, que sí lo hace de una sola vez con todo el historial
        disponible). `vela` es la misma vela gatillo que disparó la entrada —
        se alimenta primero, por si ya tocó target o stop en esa misma barra.
        Nunca bloquea ni rompe el stream: cualquier error se loguea y se
        descarta."""
        try:
            config = await get_active_config()
            if (evento.entry - evento.stop) / evento.entry * 100 < config.bp34_stop_min_pct:
                return  # mismo criterio de tradabilidad que el walker de backtest
            if not evento_en_ventana_permitida(evento.timestamp, config):
                return  # fuera de la ventana de sesión calibrada (bp34_entradas_solo_sesion_regular)
            target_r = getattr(config, f"bp34_target_r_{timeframe}")
            target = evento.entry + (evento.entry - evento.stop) * target_r
            evento_bp34 = Bp34Evento(
                ticker=ticker,
                timeframe=timeframe,
                fecha=fecha_ny(evento.timestamp),
                timestamp=evento.timestamp,
                fuente=FuenteDatos.LIVE,
                tipo=evento.tipo,
                tier=evento.tier,
                entry=evento.entry,
                stop=evento.stop,
                target=target,
                barra1_wrb_ratio=evento.barra1_wrb_ratio,
                config_snapshot=config.model_dump(mode="json"),
            )
            evento_id = await db.insert_bp34_evento(evento_bp34)
            console.log(
                f"[cyan]3BP: {ticker} ({timeframe}) entrada {evento.tipo} "
                f"tier={evento.tier} entry={evento.entry:.2f} stop={evento.stop:.2f}[/cyan]"
            )

            seguidor = SeguidorPosicion3BP(
                ticker=ticker, timeframe=timeframe, fecha=evento_bp34.fecha,
                entry=evento.entry, stop=evento.stop, target=target,
                slippage_bps=config.slippage_bps,
            )
            resultado_inmediato = seguidor.procesar_vela(vela)
            if resultado_inmediato is not None:
                await _persistir_resolucion_3bp(evento_id, ticker, timeframe, resultado_inmediato)
            else:
                app.state.market_cache.agregar_posicion_3bp_abierta(ticker, evento_id, seguidor)
        except Exception as exc:
            console.log(f"[red]Error persistiendo evento 3BP de {ticker}: {exc}[/red]")

    async def _persistir_resolucion_3bp(evento_id: int, ticker: str, timeframe: str, resultado_tuple) -> None:
        resultado, resultado_r, mfe_r, mae_r, tiempo = resultado_tuple
        try:
            await db.update_bp34_evento_resultado(evento_id, resultado.value, resultado_r, mfe_r, mae_r, tiempo)
            console.log(
                f"[cyan]3BP: {ticker} ({timeframe}) posición resuelta -> "
                f"{resultado.value} ({resultado_r:+.2f}R, {tiempo}min)[/cyan]"
            )
        except Exception as exc:
            console.log(f"[red]Error actualizando resultado 3BP de {ticker}: {exc}[/red]")

    async def _on_resolucion_3bp(
        evento_id: int, ticker: str, timeframe: str, resultado, resultado_r: float,
        mfe_r: float, mae_r: float, tiempo: int,
    ) -> None:
        await _persistir_resolucion_3bp(evento_id, ticker, timeframe, (resultado, resultado_r, mfe_r, mae_r, tiempo))

    async def _reconciliar_posiciones_3bp(tickers: list[str]) -> None:
        """Tras (re)suscribir estos tickers —nuevo CSV, o reconexión manual
        del stream después de reiniciar el servidor (POST /stream/start)—
        busca en Turso sus propias entradas 3BP/4BP que hayan quedado
        ABIERTO: pudo pasar si el servidor se cayó a mitad de sesión y nunca
        llegó a verlas resolverse. Las resuelve con el historial real de
        Schwab de ese día (SeguidorPosicion3BP alimentado de una sola vez con
        todas las velas ya transcurridas — misma clase, mismo método
        procesar_vela, que el seguimiento genuinamente en vivo). 3BP nunca
        sostiene una posición de un día para el otro, así que esto siempre
        alcanza para resolver del todo cualquier entrada de un día anterior;
        si sigue sin resolver, solo puede ser porque `evento.fecha` es HOY y
        la sesión sigue abierta — en ese caso queda re-enganchada al
        seguimiento en vivo normal. Nunca bloquea el arranque ni la
        suscripción: cualquier error se loguea y se sigue con el resto.

        Limitación conocida: solo reconcilia los tickers que se están
        (re)suscribiendo acá — un ticker con una posición abierta que no
        vuelva a aparecer en un CSV ni en /stream/start no se reconcilia
        solo. Aceptable en el uso normal (el servidor no debería estar
        caído mucho tiempo, y /stream/start ya resuscribe todo lo del
        scan de hoy)."""
        for ticker in tickers:
            try:
                abiertos = await db.get_bp34_eventos_abiertos(ticker)
            except Exception:
                continue
            for row in abiertos:
                try:
                    await _reconciliar_una_posicion_3bp(ticker, row)
                except Exception as exc:
                    console.log(f"[yellow]No se pudo reconciliar posición 3BP abierta de {ticker}: {exc}[/yellow]")

    async def _reconciliar_una_posicion_3bp(ticker: str, row: dict) -> None:
        snap = row.get("config_snapshot", "{}")
        config_snapshot = json.loads(snap) if isinstance(snap, str) else snap
        evento = Bp34Evento(**{**row, "config_snapshot": config_snapshot})

        df = await history_cache.get_history(ticker, evento.timeframe, evento.fecha, date.today())
        df = history_cache.filter_range(df, evento.fecha, evento.fecha)  # 3BP nunca sostiene overnight
        velas_desde_entrada = [v for v in _df_a_velas(df) if v.timestamp >= evento.timestamp]

        seguidor = SeguidorPosicion3BP(
            ticker=ticker, timeframe=evento.timeframe, fecha=evento.fecha,
            entry=evento.entry, stop=evento.stop, target=evento.target,
            slippage_bps=config_snapshot.get("slippage_bps", 0.0),
        )

        resultado_final = None
        for v in velas_desde_entrada:
            resultado_final = seguidor.procesar_vela(v)
            if resultado_final is not None:
                break

        if resultado_final is not None:
            await _persistir_resolucion_3bp(evento.id, ticker, evento.timeframe, resultado_final)
            console.log(f"[cyan]3BP: {ticker} ({evento.timeframe}) posición reconciliada tras reinicio[/cyan]")
        elif app.state.market_cache.agregar_posicion_3bp_abierta(ticker, evento.id, seguidor):
            console.log(f"[cyan]3BP: {ticker} ({evento.timeframe}) posición sigue abierta, re-enganchada al stream[/cyan]")
        else:
            console.log(
                f"[yellow]3BP: {ticker} ({evento.timeframe}) posición sigue abierta pero el ticker "
                "no está en el cache — no se pudo re-enganchar[/yellow]"
            )

    async def _procesar_y_conectar_stream(tickers):
        """Corre el pipeline pre-market (sembrando el cache) y arranca o
        extiende el stream — compartido por el CSV watcher (tickers nuevos
        del día) y por POST /stream/start (reconexión manual con lo que ya
        esté persistido hoy en Turso, ej. tras reiniciar el servidor sin
        que llegue un CSV nuevo — el watcher solo dispara con eventos de
        filesystem, no reprocesa lo que ya estaba en el disco)."""
        from .pipeline import run_pipeline
        config = await get_active_config()
        results = await run_pipeline(tickers, config, cache=app.state.market_cache)
        app.state.latest_results = results

        nombres = [t.ticker for t in tickers]
        # Después de sembrar el cache (ya hay un TickerCache por cada uno de
        # estos tickers) pero antes de arrancar/extender el stream — así,
        # para cuando lleguen las primeras velas, cualquier posición que
        # siga abierta ya está enganchada y lista para seguir resolviéndose.
        await _reconciliar_posiciones_3bp(nombres)

        if app.state.stream_manager is None:
            app.state.stream_manager = crear_stream_manager(
                app.state.market_cache, _on_evento_significativo, _on_evento_3bp, _on_resolucion_3bp
            )
            await app.state.stream_manager.start(nombres)
        else:
            await app.state.stream_manager.agregar_tickers(nombres)

    app.state.procesar_y_conectar_stream = _procesar_y_conectar_stream

    # ── CSV Watcher con pipeline callback ─────────────────────────────────
    loop = asyncio.get_event_loop()

    async def _pipeline_callback(tickers):
        await _procesar_y_conectar_stream(tickers)

    csv_watcher = CSVWatcher(
        Path(settings.input_folder),
        pipeline_callback=_pipeline_callback,
        loop=loop,
    )
    csv_watcher.start()
    app.state.csv_watcher = csv_watcher

    # CSV soltado en input/ mientras el servidor estaba caído — watchdog
    # solo ve eventos con el proceso vivo, así que sin esto se queda ahí
    # sin procesar indefinidamente (ver también /scan/refrescar).
    backlog = await asyncio.to_thread(csv_watcher.procesar_backlog)
    if backlog:
        console.log(f"[green]Backlog: {backlog} CSV pendiente(s) en input/ procesados[/green]")

    console.log(f"[green]Trading Scanner en http://localhost:{settings.scanner_port}[/green]")
    if settings.mock_schwab:
        console.log("[yellow]MOCK_SCHWAB=true — datos sinteticos activos[/yellow]")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    watcher = getattr(app.state, "csv_watcher", None)
    if watcher:
        watcher.stop()
    stream_manager = getattr(app.state, "stream_manager", None)
    if stream_manager:
        await stream_manager.stop()
    console.log("[green]Sistema apagado[/green]")


app = FastAPI(
    title="Trading Scanner",
    description="Sistema de scanning diario de acciones NYSE/NASDAQ",
    version="0.1.0",
    lifespan=lifespan,
)

# Static files
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Routers
app.include_router(scan_router)
app.include_router(settings_router)
app.include_router(schwab_router)
app.include_router(ticker_router)
app.include_router(config_router)
app.include_router(backtest_router)
app.include_router(stream_router)
app.include_router(optimize_router)
app.include_router(patrones_3bp_router)


# ── Dashboard ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    from .database import db

    try:
        rows = await db.get_scan_results_by_date(date.today().isoformat())
    except Exception:
        rows = []
    for r in rows:
        raw = r.get("criterios_incompletos", "[]")
        try:
            r["criterios_incompletos"] = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            r["criterios_incompletos"] = []
    rows = _dedupe_latest_por_ticker(rows)
    rows.sort(key=lambda r: r.get("confianza", 0.0), reverse=True)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "results": rows,
            "today": date.today().isoformat(),
            "mock_schwab": settings.mock_schwab,
            "schwab_estado": await estado_conexion(),
            "scanner_port": settings.scanner_port,
        },
    )


# ── Health ─────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "service": "trading-scanner",
        "version": "0.1.0",
        "mock_schwab": settings.mock_schwab,
        "turso_configured": bool(settings.turso_database_url),
        "schwab_configured": bool(settings.schwab_app_key),
        "calendar_url": settings.calendar_base_url,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "trading_scanner.main:app",
        host="0.0.0.0",
        port=settings.scanner_port,
        reload=True,
    )
