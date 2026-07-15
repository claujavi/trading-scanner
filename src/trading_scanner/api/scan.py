"""
Endpoints de scan.

GET  /scan/latest    → JSON: resultados de hoy ordenados por confianza
GET  /scan/partial   → HTML: tabla para HTMX polling desde el dashboard
GET  /scan/history   → HTML: historial de los últimos 30 días
POST /scan/upload    → recibe CSV manual, corre pipeline, redirige a /
"""

import json
import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..config import settings
from ..database import db
from ..fetchers.schwab_client import estado_conexion
from ..ingest.csv_parser import parse_csv

router = APIRouter(prefix="/scan", tags=["Scan"])


def _parse_results(rows: list[dict]) -> list[dict]:
    """Parsea criterios_incompletos de JSON string a list."""
    for r in rows:
        raw = r.get("criterios_incompletos", "[]")
        try:
            r["criterios_incompletos"] = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            r["criterios_incompletos"] = []
    return rows


def _dedupe_latest_por_ticker(rows: list[dict]) -> list[dict]:
    """Cada re-evaluación (upload manual, evento de streaming) persiste una
    fila nueva para el histórico de backtesting — nunca sobreescribe. Para
    vistas "en vivo" (dashboard, totales) nos interesa solo el estado más
    reciente de cada ticker, no todas sus re-evaluaciones acumuladas.
    """
    latest: dict[str, dict] = {}
    for r in rows:
        ticker = r.get("ticker")
        if ticker not in latest or r.get("timestamp", "") > latest[ticker].get("timestamp", ""):
            latest[ticker] = r
    return list(latest.values())


@router.get("/latest")
async def get_latest(request: Request):
    try:
        rows = await db.get_scan_results_by_date(date.today().isoformat())
    except Exception:
        rows = []
    rows = _dedupe_latest_por_ticker(_parse_results(rows))
    rows.sort(key=lambda r: r.get("confianza", 0.0), reverse=True)

    if "HX-Request" in request.headers:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="partials/scan_table.html",
            context={"results": rows},
        )

    return JSONResponse(content=rows)


@router.get("/partial", response_class=HTMLResponse)
async def get_partial(request: Request):
    try:
        rows = await db.get_scan_results_by_date(date.today().isoformat())
    except Exception:
        rows = []
    rows = _dedupe_latest_por_ticker(_parse_results(rows))
    rows.sort(key=lambda r: r.get("confianza", 0.0), reverse=True)
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/scan_table.html",
        context={"results": rows},
    )


@router.get("/history", response_class=HTMLResponse)
async def get_history(request: Request):
    try:
        rows = await db.get_scan_results_last_days(30)
    except Exception:
        rows = []
    rows = _parse_results(rows)

    # Agrupar por fecha, dedupe por ticker dentro de cada fecha
    by_date_raw: dict[str, list[dict]] = {}
    for r in rows:
        d = r.get("fecha", "")
        by_date_raw.setdefault(d, []).append(r)
    by_date = {d: _dedupe_latest_por_ticker(rs) for d, rs in by_date_raw.items()}

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "by_date": by_date,
            "mock_schwab": settings.mock_schwab,
            "schwab_estado": await estado_conexion(),
        },
    )


@router.post("/upload")
async def upload_csv(request: Request, file: UploadFile = File(...)):
    from ..pipeline import get_active_config, run_pipeline

    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        tickers = parse_csv(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    config = await get_active_config()
    results = await run_pipeline(tickers, config)
    request.app.state.latest_results = results

    return RedirectResponse("/", status_code=303)
