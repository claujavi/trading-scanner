from dataclasses import dataclass
from typing import Optional
import httpx

from ..config import settings


@dataclass
class CalendarWarning:
    nivel: str  # 'GREEN' | 'YELLOW' | 'RED'
    earnings_24h: bool
    evento_macro_24h: bool
    filing_8k_24h: bool
    upgrade_downgrade_24h: bool
    catalizador_detectado: bool
    disponible: bool


async def get_warning(ticker: str) -> CalendarWarning:
    url = f"{settings.calendar_base_url.rstrip('/')}/events/{ticker}/24h"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return CalendarWarning(
                    nivel="GREEN",
                    earnings_24h=False,
                    evento_macro_24h=False,
                    filing_8k_24h=False,
                    upgrade_downgrade_24h=False,
                    catalizador_detectado=False,
                    disponible=False,
                )
            data = resp.json()
            # Try multiple possible keys for level
            nivel = data.get("warning") or data.get("level") or data.get("status") or "GREEN"
            earnings = bool(data.get("earnings_24h") or data.get("earnings") or False)
            macro = bool(data.get("evento_macro_24h") or data.get("macro_24h") or False)
            filing = bool(data.get("filing_8k_24h") or data.get("filing") or False)
            upgrade = bool(data.get("upgrade_downgrade_24h") or data.get("upgrade") or False)
            catalizador = earnings or macro or filing or upgrade
            return CalendarWarning(
                nivel=str(nivel).upper(),
                earnings_24h=earnings,
                evento_macro_24h=macro,
                filing_8k_24h=filing,
                upgrade_downgrade_24h=upgrade,
                catalizador_detectado=bool(catalizador),
                disponible=True,
            )
    except Exception:
        # Degrade gracefully on any error (timeout, connection error, parse error)
        return CalendarWarning(
            nivel="GREEN",
            earnings_24h=False,
            evento_macro_24h=False,
            filing_8k_24h=False,
            upgrade_downgrade_24h=False,
            catalizador_detectado=False,
            disponible=False,
        )
