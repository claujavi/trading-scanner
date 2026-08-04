"""
Endpoints del módulo 3BP/4BP — señal de timing paralela, ver
docs/spec_modulo_3bp_4bp.md. Página separada del dashboard/backtest del
clasificador de 6 criterios (spec, sección 5: "no se mezcla con el score").

GET  /patrones-3bp      → eventos recientes (vivo + backtest) + form de backtest
POST /patrones-3bp/run  → corre el walker, persiste el Bp34BacktestRun, redirige
"""

import json
from datetime import date

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..backtest.metrics_3bp import run_backtest_3bp
from ..config import settings
from ..database import db
from ..fetchers.schwab_client import estado_conexion
from ..models import Bp34BacktestRun, Bp34Evento
from ..pipeline import get_active_config

router = APIRouter(prefix="/patrones-3bp", tags=["3BP/4BP"])


def _parse_evento(row: dict) -> Bp34Evento:
    row = dict(row)
    raw = row.get("config_snapshot", "{}")
    row["config_snapshot"] = json.loads(raw) if isinstance(raw, str) else raw
    return Bp34Evento(**row)


def _parse_backtest_run(row: dict) -> Bp34BacktestRun:
    row = dict(row)
    for campo, default in (("tickers", "[]"), ("config_snapshot", "{}")):
        raw = row.get(campo, default)
        row[campo] = json.loads(raw) if isinstance(raw, str) else raw
    return Bp34BacktestRun(**row)


async def _base_context() -> dict:
    return {
        "mock_schwab": settings.mock_schwab,
        "schwab_estado": await estado_conexion(),
    }


def _parse_tickers(raw: str) -> list[str]:
    separadores = raw.replace(",", "\n").replace(" ", "\n")
    return sorted({t.strip().upper() for t in separadores.splitlines() if t.strip()})


@router.get("", response_class=HTMLResponse)
async def get_patrones_3bp_page(request: Request):
    try:
        eventos_rows = await db.get_bp34_eventos(limit=100)
    except Exception:
        eventos_rows = []
    eventos = [_parse_evento(r) for r in eventos_rows]

    try:
        runs_rows = await db.get_latest_bp34_backtest_runs(limit=10)
    except Exception:
        runs_rows = []
    runs = [_parse_backtest_run(r) for r in runs_rows]

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="patrones_3bp.html",
        context={"eventos": eventos, "runs": runs, "error": None, **await _base_context()},
    )


@router.post("/run")
async def post_patrones_3bp_run(
    request: Request,
    tickers: str = Form(...),
    timeframe: str = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
):
    lista_tickers = _parse_tickers(tickers)
    if not lista_tickers or timeframe not in ("5m", "15m"):
        try:
            eventos_rows = await db.get_bp34_eventos(limit=100)
            runs_rows = await db.get_latest_bp34_backtest_runs(limit=10)
        except Exception:
            eventos_rows, runs_rows = [], []
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="patrones_3bp.html",
            context={
                "eventos": [_parse_evento(r) for r in eventos_rows],
                "runs": [_parse_backtest_run(r) for r in runs_rows],
                "error": "Especificá al menos un ticker y un timeframe válido (5m o 15m).",
                **await _base_context(),
            },
        )

    config = await get_active_config()
    resultado = await run_backtest_3bp(
        lista_tickers, timeframe, date.fromisoformat(fecha_inicio), date.fromisoformat(fecha_fin), config,
    )
    await db.insert_bp34_backtest_run(resultado.model_dump(mode="json"))

    return RedirectResponse("/patrones-3bp", status_code=303)
