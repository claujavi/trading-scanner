"""
Endpoints del stream de sesión (Sprint 2).

GET  /stream/status → estado de la conexión WebSocket (o su equivalente
mock): conectado, modo, tickers suscritos, último tick recibido.
POST /stream/start   → (re)conecta manualmente con los tickers que ya
estén persistidos hoy en Turso. Necesario porque el stream solo arranca
automáticamente cuando el CSV watcher detecta un archivo NUEVO — si el CSV
de hoy ya se procesó antes (ej. el servidor se reinició después), no hay
ningún evento de filesystem que vuelva a dispararlo.
"""

from datetime import date

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..database import db
from ..models import TickerBasico

router = APIRouter(prefix="/stream", tags=["Stream"])


def _status_payload(request: Request) -> dict:
    stream_manager = getattr(request.app.state, "stream_manager", None)
    if stream_manager is None:
        return {
            "conectado": False,
            "modo": "MOCK" if request.app.state.settings.mock_schwab else "REAL",
            "tickers_suscritos": [],
            "ultimo_tick_en": None,
            "intentos_reconexion": 0,
        }
    return stream_manager.status()


def _responder_estado(request: Request, payload: dict):
    if "HX-Request" in request.headers:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request, name="partials/stream_badge.html", context=payload,
        )
    return JSONResponse(content=payload)


@router.get("/status")
async def stream_status(request: Request):
    return _responder_estado(request, _status_payload(request))


def _float_o(valor, default: float = 0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


async def _tickers_de_hoy() -> list[TickerBasico]:
    """Reconstruye TickerBasico a partir de lo último persistido hoy por
    ticker en Turso — todo lo que necesita process_ticker() de estos campos
    es precio/variacion_diaria_pct/volumen_actual/bid/ask (relvol/atr_pct/
    volumen_promedio se recalculan siempre de las velas de Schwab, ver
    pipeline.py), así que valores stale ahí no afectan la reevaluación."""
    try:
        rows = await db.get_scan_results_by_date(date.today().isoformat())
    except Exception:
        return []

    latest: dict[str, dict] = {}
    for r in rows:
        ticker = r.get("ticker")
        if not ticker:
            continue
        if ticker not in latest or r.get("timestamp", "") > latest[ticker].get("timestamp", ""):
            latest[ticker] = r

    tickers = []
    for r in latest.values():
        try:
            tickers.append(TickerBasico(
                ticker=r["ticker"],
                precio=_float_o(r.get("precio")),
                variacion_diaria_pct=_float_o(r.get("variacion_diaria_pct")),
                volumen_actual=int(_float_o(r.get("volumen_actual"))),
                relvol=_float_o(r.get("relvol"), 1.0),
                atr_pct=_float_o(r.get("atr_pct"), 1.0),
                volumen_promedio=int(_float_o(r.get("volumen_promedio"), 1.0)),
                bid=_float_o(r["bid"]) if r.get("bid") not in (None, "", "None") else None,
                ask=_float_o(r["ask"]) if r.get("ask") not in (None, "", "None") else None,
            ))
        except Exception:
            continue
    return tickers


@router.post("/start")
async def stream_start(request: Request):
    tickers = await _tickers_de_hoy()
    if not tickers:
        return _responder_estado(request, _status_payload(request))

    await request.app.state.procesar_y_conectar_stream(tickers)
    return _responder_estado(request, _status_payload(request))


@router.delete("/tickers/{ticker}")
async def stream_quitar_ticker(request: Request, ticker: str):
    """Saca un ticker de la suscripción activa — ej. cuando Schwab no
    tiene historial para el símbolo (ADRs/preferidas con formato raro del
    CSV de ToS) y solo genera ruido en los logs sin aportar nada."""
    # Ojo: NO normalizar a mayúsculas — símbolos de preferidas de ToS como
    # "AXIApC" llevan una "p" minúscula intencional (base + "p" + clase),
    # distinta de la clave real con la que quedó suscrito el ticker.
    stream_manager = getattr(request.app.state, "stream_manager", None)
    if stream_manager is not None:
        await stream_manager.quitar_tickers([ticker])
    return _responder_estado(request, _status_payload(request))
