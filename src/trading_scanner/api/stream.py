"""
Endpoint de estado del stream de sesión (Sprint 2).

GET /stream/status → estado de la conexión WebSocket (o su equivalente
mock): conectado, modo, tickers suscritos, último tick recibido.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/stream", tags=["Stream"])


@router.get("/status")
async def stream_status(request: Request):
    stream_manager = getattr(request.app.state, "stream_manager", None)
    if stream_manager is None:
        payload = {
            "conectado": False,
            "modo": "MOCK" if request.app.state.settings.mock_schwab else "REAL",
            "tickers_suscritos": [],
            "ultimo_tick_en": None,
            "intentos_reconexion": 0,
        }
    else:
        payload = stream_manager.status()

    if "HX-Request" in request.headers:
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request, name="partials/stream_badge.html", context=payload,
        )
    return JSONResponse(content=payload)
