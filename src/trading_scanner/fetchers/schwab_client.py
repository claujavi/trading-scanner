import os
from pathlib import Path
from typing import Optional

from rich.console import Console

import schwab.auth as schwab_auth
import schwab.client as schwab_client

from ..config import settings

console = Console()

APPDATA = os.environ.get("APPDATA")
if not APPDATA:
    raise EnvironmentError("La variable de entorno APPDATA no está definida")

TOKEN_DIR = Path(APPDATA) / "trading-scanner"
TOKEN_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_PATH = TOKEN_DIR / "schwab_token.json"


def get_client() -> Optional[schwab_client.Client]:
    """Retorna un cliente Schwab con token auto-refresh."""
    api_key = settings.schwab_app_key
    app_secret = settings.schwab_app_secret

    if not api_key or not app_secret:
        console.log(
            "[yellow]Schwab API no configurada: SCHWAB_APP_KEY o SCHWAB_APP_SECRET faltan[/yellow]"
        )
        return None

    try:
        if not TOKEN_PATH.exists():
            console.log(
                f"[yellow]Token de Schwab no encontrado en {TOKEN_PATH}. "
                "Ejecuta el setup de autenticación para crear el token.[/yellow]"
            )
            return None

        client = schwab_auth.client_from_token_file(
            token_path=str(TOKEN_PATH),
            api_key=api_key,
            app_secret=app_secret,
            asyncio=False,
            enforce_enums=True,
        )
        return client
    except FileNotFoundError:
        console.log(
            f"[yellow]Token de Schwab no encontrado en {TOKEN_PATH}. "
            "No se puede inicializar el cliente.[/yellow]"
        )
        return None
    except Exception as exc:
        message = str(exc).lower()
        if "expired" in message or "invalid token" in message or "token" in message:
            console.log(
                f"[yellow]Advertencia Schwab: token expirado o inválido. {exc}[/yellow]"
            )
            return None
        console.log(f"[red]Error inicializando cliente Schwab: {exc}[/red]")
        return None
