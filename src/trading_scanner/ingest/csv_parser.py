from pathlib import Path
from typing import Iterable, Optional

import polars as pl

from ..models import TickerBasico


# Columnas obligatorias en nuestro schema interno
REQUIRED_COLUMNS = ["Symbol", "Last", "Volume"]

# Al menos una de estas debe estar presente — _variacion_diaria() ya sabe
# usar cualquiera como fuente (con fallback en cascada), pero si no viene
# ninguna preferimos fallar clarito acá en vez de seguir con todo en 0.0
# silenciosamente (que después el filtro de entrada descartaría igual, sin
# dar pista de por qué).
CHANGE_COLUMNS_ALT = ["Change%", "Ext Change%", "Net Chng", "Ext Net Chng"]

# Mapeo de nombres alternativos de TOS → nombre interno
# El orden importa: se usa el primer alias que coincida
COLUMN_ALIASES: dict[str, list[str]] = {
    "Symbol":     ["Symbol"],
    "Description": ["Description"],
    "Last":       ["Last"],
    "Change%":    ["Change%", "%Change", "Chng%", "Change"],
    "Volume":     ["Volume", "Vol"],
    "Rel Volume": ["Rel Volume", "Rel Vol", "RelVol", "Vol Index"],
    "ATR%":       ["ATR%", "ATR %", "ATR"],
    "Avg Volume": ["Avg Volume", "Avg Vol"],
    "Bid":        ["Bid"],
    "Ask":        ["Ask"],
    "Net Chng":   ["Net Chng", "NetChng", "Net Change", "Net Chg"],
    "Ext Change%": [
        "Extended Session Percent Change", "Extended Session % Change",
        "Extended Session Percent",  # por si se acorta sin "Change" al renombrar
    ],
    "Ext Net Chng": [
        "Extended Session Net Change",
        "Extended Session Net",  # por si se acorta sin "Change" al renombrar
    ],
    "Market Cap": ["Market Cap", "MarketCap"],
}


def _detect_separator(path: Path) -> str:
    """Detecta si el archivo usa tabulaciones o comas."""
    try:
        first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except Exception:
        return ","
    return "\t" if "\t" in first_line else ","


def _clean_name(name: str) -> str:
    """Colapsa espacios múltiples/tabs residuales y recorta bordes."""
    return " ".join(name.split())


def _normalize_alias(name: str) -> str:
    """Para comparar nombres de columna sin importar mayúsculas/minúsculas
    ni si el usuario usó espacio o guion bajo al renombrar la columna en
    ToS (ej. "Vol Index" == "vol_index" == "VOL INDEX")."""
    return " ".join(name.replace("_", " ").split()).lower()


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Renombra columnas con alias de TOS al nombre interno esperado.

    Los exports de ToS varían: a veces traen espacios extra al final
    ("Last "), a veces columnas fusionadas ("Symbol  Description") cuando
    el separador real no coincide exactamente con lo esperado, y el
    usuario puede haber renombrado columnas en ToS usando "_" en vez de
    espacio. Se normaliza antes de matchear alias para tolerar todo eso.
    """
    # Primero: limpiar whitespace de todos los nombres de columna
    clean_map = {col: _clean_name(col) for col in df.columns}
    if any(orig != clean for orig, clean in clean_map.items()):
        df = df.rename(clean_map)

    columnas_normalizadas = {_normalize_alias(col): col for col in df.columns}
    rename_map: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            col_real = columnas_normalizadas.get(_normalize_alias(alias))
            if col_real and col_real != canonical:
                rename_map[col_real] = canonical
                break
    if rename_map:
        df = df.rename(rename_map)

    # Columna "Symbol" fusionada con "Description" (export con separador
    # inconsistente) — se detecta por prefijo y se renombra igual, el
    # símbolo se extrae más adelante quedándose con la primera palabra.
    if "Symbol" not in df.columns:
        for col in df.columns:
            if col.startswith("Symbol") and "Description" in col:
                df = df.rename({col: "Symbol"})
                break

    return df


def _validate_columns(columns: Iterable[str]) -> None:
    cols = list(columns)
    missing = [name for name in REQUIRED_COLUMNS if name not in cols]
    if missing:
        raise ValueError(
            f"CSV inválido: faltan columnas obligatorias {missing}. "
            f"Columnas encontradas: {cols}. "
            f"Se esperan: {REQUIRED_COLUMNS}."
        )
    if not any(c in cols for c in CHANGE_COLUMNS_ALT):
        raise ValueError(
            "CSV inválido: falta alguna columna de variación diaria. "
            f"Se espera al menos una de {CHANGE_COLUMNS_ALT}. "
            f"Columnas encontradas: {cols}."
        )


def _parse_float(value) -> float:
    """Parsea un valor que puede ser string con % o coma de miles."""
    if value is None:
        return 0.0
    s = str(value).replace("%", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_optional_float(value) -> Optional[float]:
    """Como _parse_float, pero None si la columna no existe o viene vacía —
    a diferencia de las métricas obligatorias, Bid/Ask no siempre están en
    el export de ToS y no tiene sentido asumir 0.0 en ese caso."""
    if value is None:
        return None
    s = str(value).replace("%", "").replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pct_desde_net_chng(net_chng: Optional[float], last: Optional[float]) -> Optional[float]:
    """precio_anterior = Last - NetChng, % = NetChng / precio_anterior * 100."""
    if net_chng is None or last is None:
        return None
    precio_anterior = last - net_chng
    if precio_anterior == 0:
        return None
    return (net_chng / precio_anterior) * 100.0


def _variacion_diaria(row: dict) -> float:
    """% de cambio diario, con fallback en cascada porque ToS reporta 0 en
    columnas de "Regular Trading Hours" durante pre-market (la sesión
    regular todavía no arrancó):

    1. Change% (Regular Trading Hours) — sirve una vez que abre el mercado.
    2. Net Chng (regular) reconstruido con Last, si está disponible.
    3. Extended Session Percent Change — pensada específicamente para
       pre-market/after-hours.
    4. Extended Session Net Change reconstruido con Last.
    """
    last = _parse_optional_float(row.get("Last"))

    pct = _parse_float(row.get("Change%"))
    if pct != 0.0:
        return pct

    pct = _pct_desde_net_chng(_parse_optional_float(row.get("Net Chng")), last)
    if pct is not None:
        return pct

    ext_pct = _parse_optional_float(row.get("Ext Change%"))
    if ext_pct is not None and ext_pct != 0.0:
        return ext_pct

    pct = _pct_desde_net_chng(_parse_optional_float(row.get("Ext Net Chng")), last)
    if pct is not None:
        return pct

    return 0.0


def _parse_market_cap(value) -> Optional[float]:
    """Market cap en millones de USD. ToS lo exporta con sufijo M o B
    (ej: "12,512 M", "1.2 B")."""
    if value is None:
        return None
    s = str(value).replace(",", "").strip()
    if not s:
        return None
    multiplicador = 1.0
    if s.endswith("B"):
        multiplicador = 1000.0
        s = s[:-1].strip()
    elif s.endswith("M"):
        s = s[:-1].strip()
    try:
        return float(s) * multiplicador
    except ValueError:
        return None


def _parse_int(value) -> int:
    """Parsea un entero que puede tener comas de miles."""
    if value is None:
        return 0
    s = str(value).replace(",", "").strip()
    # Manejar sufijos como "M" (millones) que TOS a veces agrega
    if s.endswith("M"):
        try:
            return int(float(s[:-1]) * 1_000_000)
        except ValueError:
            return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def parse_csv(path: Path) -> list[TickerBasico]:
    """Parsea un CSV/TSV de ThinkOrSwim y devuelve una lista de TickerBasico."""
    sep = _detect_separator(path)
    df = pl.read_csv(
        path,
        separator=sep,
        truncate_ragged_lines=True,
        infer_schema_length=0,  # todas las columnas como string para evitar errores de tipo
    )

    if df.height == 0:
        return []

    df = _normalize_columns(df)
    _validate_columns(df.columns)

    rows = []
    for row in df.iter_rows(named=True):
        symbol = str(row["Symbol"]).strip().split()[0] if str(row["Symbol"]).strip() else ""
        if not symbol or symbol.lower() == "symbol":
            continue  # saltar filas vacías o de cabecera repetidas

        rows.append(
            TickerBasico(
                ticker=symbol,
                precio=_parse_float(row.get("Last")),
                variacion_diaria_pct=_variacion_diaria(row),
                volumen_actual=_parse_int(row.get("Volume")),
                relvol=_parse_float(row.get("Rel Volume")),
                atr_pct=_parse_float(row.get("ATR%")),
                volumen_promedio=_parse_int(row.get("Avg Volume")),
                bid=_parse_optional_float(row.get("Bid")),
                ask=_parse_optional_float(row.get("Ask")),
                descripcion=(str(row["Description"]).strip() or None) if row.get("Description") else None,
                market_cap_millones=_parse_market_cap(row.get("Market Cap")),
            )
        )

    return rows
