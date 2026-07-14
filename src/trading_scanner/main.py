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
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from rich.console import Console

from .api.scan import _dedupe_latest_por_ticker
from .api.scan import router as scan_router
from .api.schwab import router as schwab_router
from .api.settings import router as settings_router
from .api.ticker import router as ticker_router
from .config import settings
from .database import db
from .fetchers.schwab_client import estado_conexion
from .ingest.csv_parser import parse_csv
from .ingest.csv_watcher import CSVWatcher
from .models import ScanConfig

console = Console()

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"
_STATIC_DIR = _PROJECT_ROOT / "static"


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
    app.state.templates = templates
    app.state.settings = settings
    app.state.latest_results = []

    # ── CSV Watcher con pipeline callback ─────────────────────────────────
    loop = asyncio.get_event_loop()
    config = ScanConfig()

    async def _pipeline_callback(tickers):
        from .pipeline import run_pipeline
        results = await run_pipeline(tickers, config)
        app.state.latest_results = results

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
