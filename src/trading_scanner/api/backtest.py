"""
Endpoints de backtesting.

GET  /backtest       → form (tickers + rango de fechas) + lista de runs previos
POST /backtest/run   → corre el backtest con la config activa, persiste y redirige al detalle
GET  /backtest/{id}  → detalle de un run
"""

import json

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..backtest.runner import run_backtest
from ..config import settings
from ..database import db
from ..fetchers.schwab_client import estado_conexion
from ..models import BacktestRun
from ..pipeline import get_active_config

router = APIRouter(prefix="/backtest", tags=["Backtest"])


async def _base_context() -> dict:
    return {
        "mock_schwab": settings.mock_schwab,
        "schwab_estado": await estado_conexion(),
    }


def _parse_tickers(raw: str) -> list[str]:
    separadores = raw.replace(",", "\n").replace(" ", "\n")
    return sorted({t.strip().upper() for t in separadores.splitlines() if t.strip()})


def _parse_run(row: dict) -> BacktestRun:
    """Turso devuelve todo como texto crudo — reconstruir el modelo tipado
    (Pydantic castea "33.3" → float, etc.) para que el template pueda
    formatear los números sin que Jinja rompa con un string."""
    row = dict(row)
    for campo in ("tickers", "config_snapshot"):
        raw = row.get(campo, "[]" if campo == "tickers" else "{}")
        row[campo] = json.loads(raw) if isinstance(raw, str) else raw
    return BacktestRun(**row)


@router.get("", response_class=HTMLResponse)
async def get_backtest_page(request: Request):
    try:
        rows = await db.get_latest_backtest_runs(limit=10)
    except Exception:
        rows = []
    runs = [_parse_run(r) for r in rows]

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="backtest.html",
        context={"runs": runs, "run": None, "error": None, **await _base_context()},
    )


@router.get("/{backtest_id}", response_class=HTMLResponse)
async def get_backtest_detail(request: Request, backtest_id: int):
    try:
        rows = await db.get_latest_backtest_runs(limit=10)
    except Exception:
        rows = []
    runs = [_parse_run(r) for r in rows]

    row = await db.get_backtest_run(backtest_id)
    run = _parse_run(row) if row else None

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="backtest.html",
        context={"runs": runs, "run": run, "error": None, **await _base_context()},
    )


@router.post("/run")
async def post_backtest_run(
    request: Request,
    tickers: str = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
):
    from datetime import date

    lista_tickers = _parse_tickers(tickers)
    if not lista_tickers:
        try:
            runs = await db.get_latest_backtest_runs(limit=10)
        except Exception:
            runs = []
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="backtest.html",
            context={
                "runs": runs, "run": None,
                "error": "No se especificó ningún ticker.",
                **await _base_context(),
            },
        )

    config = await get_active_config()
    resultado: BacktestRun = await run_backtest(
        lista_tickers,
        date.fromisoformat(fecha_inicio),
        date.fromisoformat(fecha_fin),
        config,
    )
    backtest_id = await db.insert_backtest_run(resultado.model_dump(mode="json"))

    return RedirectResponse(f"/backtest/{backtest_id}", status_code=303)
