"""
FastAPI application principal.

Lifespan:
- Inicializa las tablas en Turso al arrancar
- Limpia recursos al apagar

Routers:
- /scan - endpoints de scanning
- /ticker - detalle de tickers
- /config - configuración
- /backtest - backtesting
- / - status
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .config import settings
from .database import db
from .ingest.csv_watcher import CSVWatcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Context manager para el lifespan de la app.

    Startup: Inicializa el schema de Turso
    Shutdown: Limpia recursos
    """
    # ─── STARTUP ────────────────────────────────────────────────────────────
    try:
        await db.initialize_schema()
        print("✓ Schema de Turso inicializado correctamente")
    except Exception as e:
        print(f"⚠ Error inicializando schema de Turso: {e}")
        print("  El sistema continuará, pero algunas operaciones pueden fallar")

    csv_watcher = CSVWatcher(Path(settings.input_folder))
    csv_watcher.start()
    app.state.csv_watcher = csv_watcher

    yield

    # ─── SHUTDOWN ─────────────────────────────────────────────────────────────────
    watcher = getattr(app.state, "csv_watcher", None)
    if watcher is not None:
        watcher.stop()
    print("✓ Sistema apagado correctamente")


# ════════════════════════════════════════════════════════════════════════════
# FastAPI App
# ════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Trading Scanner",
    description="Sistema de scanning diario de acciones del mercado estadounidense",
    version="0.1.0",
    lifespan=lifespan,
)


# ════════════════════════════════════════════════════════════════════════════
# Health Check
# ════════════════════════════════════════════════════════════════════════════


@app.get("/", tags=["Health"])
async def health() -> dict:
    """Status del sistema."""
    return {
        "status": "ok",
        "service": "trading-scanner",
        "version": "0.1.0",
        "port": settings.scanner_port,
    }


@app.get("/health", tags=["Health"])
async def health_detailed() -> dict:
    """Health check detallado."""
    return {
        "status": "ok",
        "turso_configured": bool(settings.turso_database_url),
        "schwab_configured": bool(settings.schwab_app_key),
        "calendar_url": settings.calendar_base_url,
    }


# ════════════════════════════════════════════════════════════════════════════
# Placeholder Routers (se implementarán en sprints posteriores)
# ════════════════════════════════════════════════════════════════════════════


@app.get("/scan/latest", tags=["Scan"])
async def get_latest_scan() -> dict:
    """Obtiene el último scan del día."""
    return {"message": "Endpoint en desarrollo"}


@app.post("/scan/upload", tags=["Scan"])
async def upload_csv() -> dict:
    """Recibe un CSV de ToS."""
    return {"message": "Endpoint en desarrollo"}


@app.get("/config", tags=["Config"])
async def get_config() -> dict:
    """Obtiene la configuración actual."""
    return {"message": "Endpoint en desarrollo"}


@app.post("/config", tags=["Config"])
async def update_config() -> dict:
    """Actualiza la configuración."""
    return {"message": "Endpoint en desarrollo"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "trading_scanner.main:app",
        host="0.0.0.0",
        port=settings.scanner_port,
        reload=True,
    )
