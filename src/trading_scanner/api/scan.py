"""
Endpoints de scan.

GET  /scan/latest    → JSON: resultados de hoy ordenados por confianza
GET  /scan/partial   → HTML: tabla para HTMX polling desde el dashboard
GET  /scan/history   → HTML: historial de los últimos 30 días
POST /scan/upload    → recibe CSV manual, corre pipeline, redirige a /
"""

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..database import db
from ..ingest.csv_parser import parse_csv
from ..models import ScanConfig

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


@router.get("/latest")
async def get_latest(request: Request):
    try:
        rows = await db.get_scan_results_by_date(date.today().isoformat())
    except Exception:
        rows = []
    rows = _parse_results(rows)
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
    rows = _parse_results(rows)
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

    # Agrupar por fecha
    by_date: dict[str, list[dict]] = {}
    for r in rows:
        d = r.get("fecha", "")
        by_date.setdefault(d, []).append(r)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"by_date": by_date},
    )


@router.post("/upload")
async def upload_csv(request: Request, file: UploadFile = File(...)):
    from ..pipeline import run_pipeline

    content = await file.read()
    tmp_path = Path(request.app.state.settings.input_folder) / f"upload_{file.filename}"
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(content)

    try:
        tickers = parse_csv(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    config = ScanConfig()
    results = await run_pipeline(tickers, config)
    request.app.state.latest_results = results

    return RedirectResponse("/", status_code=303)
