from typing import Any, Dict, Iterable, Optional

from rich.console import Console

from .schwab_client import get_client

console = Console()


def _find_value(data: Any, keys: Iterable[str]) -> Optional[float]:
    if isinstance(data, dict):
        for key, value in data.items():
            if any(k in key.lower() for k in keys) and isinstance(value, (int, float)):
                return float(value)
            result = _find_value(value, keys)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_value(item, keys)
            if result is not None:
                return result
    return None


def get_ivr(ticker: str) -> Optional[float]:
    client = get_client()
    if client is None:
        console.log(f"[yellow]IVR {ticker}: cliente Schwab no disponible — criterio omitido[/yellow]")
        return None

    try:
        resp = client.get_option_chain(ticker, include_underlying_quote=True)
    except Exception as exc:
        console.log(f"[red]Error consultando opciones Schwab para {ticker}: {exc}[/red]")
        return None

    if resp.status_code != 200:
        console.log(
            f"[yellow]Opciones no disponibles para {ticker}: status {resp.status_code}[/yellow]"
        )
        return None

    payload = resp.json()
    if not isinstance(payload, dict):
        return None

    iv_actual = _find_value(payload, ["iv", "volatility", "impliedvolatility", "implied_volatility"])
    iv_min = _find_value(payload, ["min52", "52w_low", "52wlow", "min_52w", "low_52w", "volatility52wlow", "volatility52_wo", "volatility_low_52w"])
    iv_max = _find_value(payload, ["max52", "52w_high", "52whigh", "max_52w", "high_52w", "volatility52whigh", "volatility_high_52w"])

    if iv_actual is None or iv_min is None or iv_max is None:
        return None

    if iv_max - iv_min == 0:
        return None

    return (iv_actual - iv_min) / (iv_max - iv_min) * 100
