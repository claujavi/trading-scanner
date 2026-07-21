"""
Endpoints de backtesting.

GET  /backtest       → form (tickers + rango de fechas) + lista de runs previos
POST /backtest/run   → corre el backtest con la config activa, persiste y redirige al detalle
GET  /backtest/{id}  → detalle de un run
"""

import json
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..backtest.runner import run_backtest, run_backtest_universo_real, universo_real_csv
from ..config import settings
from ..database import db
from ..fetchers.schwab_client import estado_conexion
from ..models import BacktestRun
from ..pipeline import get_active_config

router = APIRouter(prefix="/backtest", tags=["Backtest"])

_INPUT_FOLDER = Path(settings.input_folder)


async def _base_context() -> dict:
    dias = sorted(universo_real_csv(_INPUT_FOLDER).keys())
    return {
        "mock_schwab": settings.mock_schwab,
        "schwab_estado": await estado_conexion(),
        "dias_universo_real": [d.isoformat() for d in dias],
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


@router.post("/run-universo-real")
async def post_backtest_run_universo_real(request: Request):
    config = await get_active_config()
    try:
        resultado: BacktestRun = await run_backtest_universo_real(config, _INPUT_FOLDER)
    except ValueError as exc:
        try:
            runs = await db.get_latest_backtest_runs(limit=10)
        except Exception:
            runs = []
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="backtest.html",
            context={
                "runs": [_parse_run(r) for r in runs], "run": None,
                "error": str(exc),
                **await _base_context(),
            },
        )

    backtest_id = await db.insert_backtest_run(resultado.model_dump(mode="json"))
    return RedirectResponse(f"/backtest/{backtest_id}", status_code=303)
