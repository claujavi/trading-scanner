"""
Endpoints de configuración y credenciales.

GET  /settings → página de configuración con estado de cada servicio
POST /settings → guarda credenciales en .env (requiere reinicio para que tomen efecto)
"""

from pathlib import Path

import httpx
from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import settings

router = APIRouter(prefix="/settings", tags=["Settings"])

_ENV_PATH = Path(".env")


def _mask(value: str) -> str:
    if not value or len(value) <= 4:
        return "****"
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


async def _check_turso() -> bool:
    if not settings.turso_database_url or not settings.turso_auth_token:
        return False
    try:
        base = settings.turso_database_url.replace("libsql://", "https://")
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(
                f"{base}/v2/pipeline",
                headers={
                    "Authorization": f"Bearer {settings.turso_auth_token}",
                    "Content-Type": "application/json",
                },
                json={"requests": [{"type": "execute", "stmt": {"sql": "SELECT 1"}}]},
            )
            return r.status_code < 400
    except Exception:
        return False


async def _check_calendar() -> bool:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{settings.calendar_base_url}/health")
            return r.status_code == 200
    except Exception:
        return False


@router.get("", response_class=HTMLResponse)
async def get_settings(request: Request):
    turso_ok, calendar_ok = await _check_turso(), await _check_calendar()
    schwab_configured = bool(settings.schwab_app_key and settings.schwab_app_secret)

    context = {
        "request": request,
        "turso_url_masked": _mask(settings.turso_database_url),
        "turso_token_masked": _mask(settings.turso_auth_token),
        "schwab_key_masked": _mask(settings.schwab_app_key),
        "schwab_secret_masked": _mask(settings.schwab_app_secret),
        "calendar_url": settings.calendar_base_url,
        "turso_ok": turso_ok,
        "calendar_ok": calendar_ok,
        "schwab_configured": schwab_configured,
        "mock_schwab": settings.mock_schwab,
        "scanner_port": settings.scanner_port,
    }

    templates = request.app.state.templates
    # Remove 'request' from context since Starlette 1.x passes it separately
    context.pop("request", None)
    return templates.TemplateResponse(request=request, name="settings.html", context=context)


@router.post("")
async def save_settings(
    turso_database_url: str = Form(""),
    turso_auth_token: str = Form(""),
    schwab_app_key: str = Form(""),
    schwab_app_secret: str = Form(""),
    calendar_base_url: str = Form("http://localhost:8000"),
):
    env_lines: dict[str, str] = {}

    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                env_lines[k.strip()] = v.strip()

    updates = {
        "TURSO_DATABASE_URL": turso_database_url,
        "TURSO_AUTH_TOKEN": turso_auth_token,
        "SCHWAB_APP_KEY": schwab_app_key,
        "SCHWAB_APP_SECRET": schwab_app_secret,
        "CALENDAR_BASE_URL": calendar_base_url,
    }
    for k, v in updates.items():
        if v:
            env_lines[k] = v

    _ENV_PATH.write_text(
        "\n".join(f"{k}={v}" for k, v in env_lines.items()) + "\n",
        encoding="utf-8",
    )

    return RedirectResponse("/settings?saved=1", status_code=303)
