from pathlib import Path
from typing import Iterable

import polars as pl

from ..models import TickerBasico


# Columnas obligatorias en nuestro schema interno
REQUIRED_COLUMNS = ["Symbol", "Last", "Change%", "Volume"]

# Mapeo de nombres alternativos de TOS → nombre interno
# El orden importa: se usa el primer alias que coincida
COLUMN_ALIASES: dict[str, list[str]] = {
    "Symbol":     ["Symbol"],
    "Last":       ["Last"],
    "Change%":    ["Change%", "%Change", "Chng%", "Change"],
    "Volume":     ["Volume", "Vol"],
    "Rel Volume": ["Rel Volume", "Rel Vol", "RelVol", "Vol Index"],
    "ATR%":       ["ATR%", "ATR %", "ATR"],
    "Avg Volume": ["Avg Volume", "Avg Vol"],
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


def _normalize_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Renombra columnas con alias de TOS al nombre interno esperado.

    Los exports de ToS varían: a veces traen espacios extra al final
    ("Last "), a veces columnas fusionadas ("Symbol  Description") cuando
    el separador real no coincide exactamente con lo esperado. Se limpia
    el whitespace antes de matchear alias para tolerar esas variaciones.
    """
    # Primero: limpiar whitespace de todos los nombres de columna
    clean_map = {col: _clean_name(col) for col in df.columns}
    if any(orig != clean for orig, clean in clean_map.items()):
        df = df.rename(clean_map)

    rename_map: dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns and alias != canonical:
                rename_map[alias] = canonical
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


def _parse_float(value) -> float:
    """Parsea un valor que puede ser string con % o coma de miles."""
    if value is None:
        return 0.0
    s = str(value).replace("%", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


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
                variacion_diaria_pct=_parse_float(row.get("Change%")),
                volumen_actual=_parse_int(row.get("Volume")),
                relvol=_parse_float(row.get("Rel Volume")),
                atr_pct=_parse_float(row.get("ATR%")),
                volumen_promedio=_parse_int(row.get("Avg Volume")),
            )
        )

    return rows
