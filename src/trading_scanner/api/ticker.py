"""
Endpoint de detalle por ticker.

GET /ticker/{ticker} → última evaluación con desglose por criterio +
                       historial de evaluaciones previas de ese ticker
"""

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..config import settings
from ..database import db
from ..engine.evaluator import desglosar_criterios
from ..fetchers.schwab_client import estado_conexion
from ..models import ScanResult

router = APIRouter(prefix="/ticker", tags=["Ticker"])


def _parse_row(row: dict) -> dict:
    raw_criterios = row.get("criterios_incompletos", "[]")
    row["criterios_incompletos"] = (
        json.loads(raw_criterios) if isinstance(raw_criterios, str) else raw_criterios
    )
    raw_snapshot = row.get("config_snapshot", "{}")
    row["config_snapshot"] = (
        json.loads(raw_snapshot) if isinstance(raw_snapshot, str) else raw_snapshot
    )
    return row


@router.get("/{ticker}", response_class=HTMLResponse)
async def ticker_detail(request: Request, ticker: str):
    ticker = ticker.upper()
    try:
        rows = await db.get_scan_results_by_ticker(ticker, limit=30)
    except Exception:
        rows = []

    templates = request.app.state.templates
    base_context = {
        "mock_schwab": settings.mock_schwab,
        "schwab_estado": await estado_conexion(),
    }

    if not rows:
        return templates.TemplateResponse(
            request=request,
            name="ticker_detail.html",
            context={
                "ticker": ticker, "result": None, "desglose": [], "historial": [],
                **base_context,
            },
        )

    rows = [_parse_row(dict(r)) for r in rows]
    latest = ScanResult(**rows[0])
    desglose = desglosar_criterios(latest)
    filtros_violados = [
        c.removeprefix("FILTRO_ENTRADA:")
        for c in latest.criterios_incompletos
        if c.startswith("FILTRO_ENTRADA:")
    ]

    return templates.TemplateResponse(
        request=request,
        name="ticker_detail.html",
        context={
            "ticker": ticker,
            "result": latest,
            "desglose": desglose,
            "historial": rows[1:],
            "filtros_violados": filtros_violados,
            **base_context,
        },
    )
