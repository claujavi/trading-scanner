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

from rich.console import Console

from .api.backtest import router as backtest_router
from .api.config import router as config_router
from .api.scan import _dedupe_latest_por_ticker
from .api.scan import router as scan_router
from .api.schwab import router as schwab_router
from .api.settings import router as settings_router
from .api.stream import router as stream_router
from .api.ticker import router as ticker_router
from .config import settings
from .database import db
from .fetchers.market_data_cache import MarketDataCache
from .fetchers.schwab_client import estado_conexion
from .fetchers.schwab_stream import crear_stream_manager
from .ingest.csv_parser import parse_csv
from .ingest.csv_watcher import CSVWatcher

console = Console()

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
        if app.state.stream_manager is None:
            app.state.stream_manager = crear_stream_manager(
                app.state.market_cache, _on_evento_significativo
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
