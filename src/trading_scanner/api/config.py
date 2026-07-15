"""
Endpoints de configuración paramétrica (ScanConfig).

GET  /config → formulario con la config activa (última guardada, o defaults)
POST /config → guarda una nueva config y pasa a ser la activa desde el
               próximo scan (sin reiniciar el servidor)
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from ..config import settings
from ..database import db
from ..fetchers.schwab_client import estado_conexion
from ..models import ModoSalida, ScanConfig
from ..pipeline import get_active_config

router = APIRouter(prefix="/config", tags=["Config"])


async def _base_context() -> dict:
    return {
        "mock_schwab": settings.mock_schwab,
        "schwab_estado": await estado_conexion(),
    }


@router.get("", response_class=HTMLResponse)
async def get_config_page(request: Request):
    config = await get_active_config()
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="config.html",
        context={
            "config": config,
            "modos_salida": list(ModoSalida),
            "error": None,
            **await _base_context(),
        },
    )


@router.post("")
async def save_config(request: Request):
    form = await request.form()
    data = dict(form)

    try:
        config = ScanConfig(**data)
    except ValidationError as exc:
        current = await get_active_config()
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="config.html",
            context={
                "config": current,
                "modos_salida": list(ModoSalida),
                "error": str(exc),
                **await _base_context(),
            },
        )

    await db.insert_scan_config(config.model_dump(mode="json"))
    return RedirectResponse("/config?saved=1", status_code=303)
