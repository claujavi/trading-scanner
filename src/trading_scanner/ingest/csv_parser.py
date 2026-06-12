from pathlib import Path
from typing import Iterable

import polars as pl

from ..models import TickerBasico


REQUIRED_COLUMNS = ["Symbol", "Last", "Change%", "Volume", "ATR%"]
OPTIONAL_COLUMNS = ["Rel Volume", "Avg Volume"]


def _validate_columns(columns: Iterable[str]) -> None:
    missing = [name for name in REQUIRED_COLUMNS if name not in columns]
    if missing:
        raise ValueError(
            f"CSV inválido: faltan columnas obligatorias {missing}. "
            f"Se esperan: {REQUIRED_COLUMNS}."
        )


def parse_csv(path: Path) -> list[TickerBasico]:
    """Parsea un CSV de ThinkOrSwim y devuelve una lista de TickerBasico."""
    df = pl.read_csv(path)

    if df.height == 0:
        return []

    _validate_columns(df.columns)

    rows = []
    for row in df.iter_rows(named=True):
        symbol = row["Symbol"]
        last = float(row["Last"])
        change_pct = float(row["Change%"])
        volume = int(row["Volume"])
        atr_pct = float(row["ATR%"])

        relvol = float(row.get("Rel Volume", 0.0)) if row.get("Rel Volume") is not None else 0.0
        avg_volume = int(row.get("Avg Volume", 0)) if row.get("Avg Volume") is not None else 0

        rows.append(
            TickerBasico(
                ticker=symbol,
                precio=last,
                variacion_diaria_pct=change_pct,
                volumen_actual=volume,
                relvol=relvol,
                atr_pct=atr_pct,
                volumen_promedio=avg_volume,
            )
        )

    return rows
