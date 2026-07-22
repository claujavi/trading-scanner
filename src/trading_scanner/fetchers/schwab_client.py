import asyncio
import json
import os
import time
from datetime import date, datetime, time as dtime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import httpx
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


REFRESH_TOKEN_MAX_AGE_DIAS = 7
"""Documentado oficialmente por Schwab (PDF "Accounts and Trading Production"
del Developer Portal, ver docs/schwab-api/RESUMEN.md) y confirmado también
empíricamente antes de encontrar esa referencia: un token de 21 días fue
rechazado con invalid_grant."""


def info_token() -> Optional[dict]:
    """Metadata legible del token actual: fecha de creación y edad en días.

    None si no hay token o el archivo no se puede leer.
    """
    if not TOKEN_PATH.exists():
        return None
    try:
        with open(TOKEN_PATH, encoding="utf-8") as f:
            data = json.load(f)
        ts = data.get("creation_timestamp")
        if ts is None:
            return None
        return {
            "creado_en": datetime.fromtimestamp(ts),
            "edad_dias": (time.time() - ts) / 86400,
        }
    except Exception:
        return None


def iniciar_conexion() -> schwab_auth.AuthContext:
    """Genera el link de login OAuth2 (sin bloquear ni abrir browser).

    Pensado para el flujo de webapp de schwab-py: el caller muestra
    `authorization_url` al usuario y luego llama a `completar_conexion()`
    con la URL de redirect que el usuario pega de vuelta.
    """
    return schwab_auth.get_auth_context(
        settings.schwab_app_key,
        settings.schwab_callback_url,
    )


def completar_conexion(received_url: str, auth_context: schwab_auth.AuthContext) -> None:
    """Completa el login OAuth2 con la URL de redirect pegada por el usuario.

    Propaga cualquier excepción de authlib (state mismatch, code faltante,
    intercambio rechazado) — el caller la captura y muestra el error.
    """

    def _token_write_func(token: dict) -> None:
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(token, f)

    schwab_auth.client_from_received_url(
        settings.schwab_app_key,
        settings.schwab_app_secret,
        auth_context,
        received_url,
        _token_write_func,
        asyncio=False,
        enforce_enums=True,
    )
    _invalidar_cache_estado()


def _verificar_conexion_real() -> str:
    """Confirma que el token no solo carga, sino que Schwab lo acepta.

    get_account_numbers() es la llamada más liviana de la API (solo
    devuelve los hashes de cuenta, sin saldos ni posiciones): sirve como
    "ping" de sesión sin gastar rate limit de forma significativa.

    El chequeo de edad del token (barato, sin red) ya se hizo antes en
    estado_conexion() — acá solo se llega si el token todavía no cruzó
    el umbral de edad conocido (REFRESH_TOKEN_MAX_AGE_DIAS).
    """
    client = get_client()
    if client is None:
        return "DESCONECTADO"
    try:
        resp = client.get_account_numbers()
        return "ON_LINE" if resp.status_code == 200 else "DESCONECTADO"
    except Exception as exc:
        console.log(f"[yellow]Schwab: token rechazado al verificar conexión. {exc}[/yellow]")
        return "DESCONECTADO"


NY_TZ = ZoneInfo("America/New_York")

# Feriados de NYSE, respaldo local si Trading Calendar no responde (mismo
# principio que calendar_client.py: nunca bloquear por su ausencia). Fuente
# primaria: GET {calendar_base_url}/calendar/holidays/{year}. Si eso falla,
# se cae a esta lista fija — desactualizada, el único efecto es una llamada
# real de más a Schwab ese día puntual, no rompe nada.
FERIADOS_NYSE_FALLBACK: set[date] = {
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
    date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
    date(2027, 11, 25), date(2027, 12, 24),
}

_VENTANA_INICIO = dtime(7, 0)
_VENTANA_FIN = dtime(17, 0)

# Ventana específica del bloqueo del optimizador (api/optimize.py) — más
# angosta que _VENTANA_INICIO/_VENTANA_FIN de arriba, que existen para otra
# cosa (decidir cuándo vale la pena chequear el estado de conexión Schwab, no
# para minimizar el riesgo de competir por CPU con Optuna). El trader corre
# el scanner ~30 min antes de la apertura (9:30 NY) y el stream puede seguir
# activo un rato después del cierre (16:00) cerrando posiciones — de ahí
# 8:30–16:30, no la ventana amplia de pre/post-market de _en_horario_habil().
_VENTANA_BLOQUEO_OPTIMIZADOR_INICIO = dtime(8, 30)
_VENTANA_BLOQUEO_OPTIMIZADOR_FIN = dtime(16, 30)

# Cache de feriados por año — se piden una sola vez a Trading Calendar y
# quedan en memoria el resto de la vida del proceso (los feriados de un
# año no cambian una vez publicados).
_feriados_cache: dict[int, set[date]] = {}


async def _obtener_feriados(year: int) -> set[date]:
    if year in _feriados_cache:
        return _feriados_cache[year]

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.calendar_base_url}/calendar/holidays/{year}")
            resp.raise_for_status()
            data = resp.json()
            feriados = {date.fromisoformat(d) for d in data["holidays"]}
    except Exception:
        console.log(
            f"[yellow]No se pudo obtener feriados NYSE de Trading Calendar "
            f"para {year} — usando lista local de respaldo.[/yellow]"
        )
        feriados = {d for d in FERIADOS_NYSE_FALLBACK if d.year == year}

    _feriados_cache[year] = feriados
    return feriados


async def _en_ventana(inicio: dtime, fin: dtime) -> bool:
    """Lun-vie, sin feriados NYSE, dentro de [inicio, fin] hora de Nueva York.

    Usar ZoneInfo("America/New_York") evita calcular a mano el offset
    entre Argentina y Nueva York, que cambia con el horario de verano/
    invierno de EE.UU. — la comparación siempre es contra la hora de NY.
    """
    ahora = datetime.now(NY_TZ)
    if ahora.weekday() >= 5:  # sábado=5, domingo=6
        return False
    feriados = await _obtener_feriados(ahora.year)
    if ahora.date() in feriados:
        return False
    return inicio <= ahora.time() <= fin


async def _en_horario_habil() -> bool:
    """Ventana amplia (7:00–17:00 ET) — cubre pre-market (cuando llega el CSV
    de ToS y el pipeline sí necesita Schwab en vivo) hasta un rato después del
    cierre. Usada para decidir cuándo vale la pena verificar la conexión
    Schwab en vivo (estado_conexion()), no para el bloqueo del optimizador."""
    return await _en_ventana(_VENTANA_INICIO, _VENTANA_FIN)


async def en_horario_habil() -> bool:
    """Wrapper público de _en_horario_habil() — usado donde se necesite saber
    si vale la pena golpear a Schwab en vivo (no confundir con
    en_ventana_bloqueo_optimizador(), que es una ventana distinta y más
    angosta pensada específicamente para el optimizador)."""
    return await _en_horario_habil()


async def en_ventana_bloqueo_optimizador() -> bool:
    """8:30–16:30 ET — ventana en la que api/optimize.py bloquea sin
    excepción el botón de correr el optimizador (compite por CPU con el
    scanner en vivo). Ver comentario junto a _VENTANA_BLOQUEO_OPTIMIZADOR_*
    arriba sobre por qué es distinta de en_horario_habil()."""
    return await _en_ventana(_VENTANA_BLOQUEO_OPTIMIZADOR_INICIO, _VENTANA_BLOQUEO_OPTIMIZADOR_FIN)


# Cache corto del resultado de _verificar_conexion_real(): cada carga de
# página (/, /settings, /scan/history) llamaría a Schwab si no cacheáramos.
# Particularmente importante con un token vencido — sin esto, cada navegación
# reintenta el refresh OAuth con un refresh_token inválido contra el servidor
# de Schwab, lo que en volumen puede leerse como abuso del lado de Schwab.
_ESTADO_CACHE_TTL = 300  # segundos
_estado_cache: dict = {"valor": None, "expira": 0.0}


def _invalidar_cache_estado() -> None:
    _estado_cache["valor"] = None
    _estado_cache["expira"] = 0.0


async def estado_conexion() -> str:
    """Única fuente de verdad del estado de conexión con Schwab.

    Retorna "MOCK", "SIN_CREDENCIALES", "ON_LINE" o "DESCONECTADO".
    Usado por todas las rutas que renderizan el header — evitar duplicar
    este chequeo en cada endpoint.
    """
    if settings.mock_schwab:
        return "MOCK"
    if not settings.schwab_app_key or not settings.schwab_app_secret:
        return "SIN_CREDENCIALES"

    # Chequeo de edad del token: no pega a la red, así que corre siempre,
    # sin importar el horario hábil ni el cache — evita mostrar "ON_LINE"
    # con datos viejos si nadie cargó una página en horario hábil desde
    # que el token venció (el filtro de horario de abajo solo protege la
    # llamada REAL a Schwab, no este chequeo local).
    info = info_token()
    if info is not None and info["edad_dias"] >= REFRESH_TOKEN_MAX_AGE_DIAS:
        console.log(
            f"[yellow]Token de Schwab con {info['edad_dias']:.1f} días — "
            f"se asume vencido sin llamar a la API.[/yellow]"
        )
        _estado_cache["valor"] = "DESCONECTADO"
        _estado_cache["expira"] = time.monotonic() + _ESTADO_CACHE_TTL
        return "DESCONECTADO"

    if not await _en_horario_habil():
        # Fuera de horario/día hábil: no tiene sentido gastar una llamada
        # real a Schwab (fin de semana, feriado, madrugada). Se reusa el
        # último estado conocido, sin importar si el TTL normal ya venció.
        return _estado_cache["valor"] or "DESCONECTADO"

    now = time.monotonic()
    if _estado_cache["valor"] is not None and now < _estado_cache["expira"]:
        return _estado_cache["valor"]

    resultado = await asyncio.to_thread(_verificar_conexion_real)
    _estado_cache["valor"] = resultado
    _estado_cache["expira"] = now + _ESTADO_CACHE_TTL
    return resultado
