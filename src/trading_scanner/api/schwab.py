"""
Endpoints para conectar la cuenta de Schwab (flujo OAuth2 de webapp).

GET  /schwab/connect → muestra el link de login y el form para pegar la
                        URL de redirect
POST /schwab/connect → completa el intercambio OAuth2 y persiste el token
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..fetchers.schwab_client import (
    completar_conexion,
    estado_conexion,
    iniciar_conexion,
)

router = APIRouter(prefix="/schwab", tags=["Schwab"])


@router.get("/connect", response_class=HTMLResponse)
async def get_connect(request: Request):
    estado = await estado_conexion()
    templates = request.app.state.templates

    if estado in ("MOCK", "SIN_CREDENCIALES"):
        return templates.TemplateResponse(
            request=request,
            name="schwab_connect.html",
            context={"estado": estado, "authorization_url": None, "error": None},
        )

    auth_context = iniciar_conexion()
    request.app.state.schwab_auth_context = auth_context

    return templates.TemplateResponse(
        request=request,
        name="schwab_connect.html",
        context={
            "estado": estado,
            "ya_conectado": estado == "ON_LINE",
            "authorization_url": auth_context.authorization_url,
            "error": None,
        },
    )


@router.post("/connect", response_class=HTMLResponse)
async def post_connect(request: Request, received_url: str = Form(...)):
    auth_context = getattr(request.app.state, "schwab_auth_context", None)
    templates = request.app.state.templates

    if auth_context is None:
        return templates.TemplateResponse(
            request=request,
            name="schwab_connect.html",
            context={
                "estado": "DESCONECTADO",
                "authorization_url": None,
                "error": (
                    "No se encontró el intento de conexión en curso "
                    "(¿se reinició el servidor?). Volvé a empezar."
                ),
            },
        )

    try:
        completar_conexion(received_url, auth_context)
    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="schwab_connect.html",
            context={
                "estado": "DESCONECTADO",
                "authorization_url": auth_context.authorization_url,
                "error": f"No se pudo completar la conexión: {exc}",
            },
        )

    request.app.state.schwab_auth_context = None
    return RedirectResponse("/?schwab=ok", status_code=303)
