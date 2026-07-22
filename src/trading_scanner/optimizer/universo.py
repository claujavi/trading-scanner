"""
universo.py — fuentes de universo para el optimizador.

study.py no sabe (ni le importa) de dónde salen los datos que evalúa en
cada trial — solo llama a FuenteUniverso.recolectar(config). Esto permite
dos fuentes intercambiables:

- universo_real(): fiel a lo que ToS mostró (CSV guardados en input/ e
  input/processed/) — la fuente correcta para calibrar parámetros según
  CLAUDE.md, pero limitada a los días que ya se exportaron.
- universo_curado(): lista fija de tickers conocidos como volátiles contra
  un rango de fechas arbitrario (años de historial de Schwab) — más
  volumen de datos para una optimización con mejor significancia
  estadística mientras se acumulan más días reales, pero mide algo
  distinto (qué tan bien puntúa el evaluador sobre nombres ya sabidos
  como volátiles, no fidelidad de descubrimiento real — ver runner.py).
  Cualquier config que salga de acá debería revalidarse después contra
  universo_real() cuando haya más días de CSV disponibles.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Awaitable, Callable

from ..models import ScanConfig
from ..backtest.metrics import ResultadoDia
from ..backtest.runner import (
    recolectar_resultados,
    recolectar_resultados_universo_real,
    universo_real_csv,
)

RecolectorResultados = Callable[[ScanConfig], Awaitable[list[ResultadoDia]]]


@dataclass
class FuenteUniverso:
    tickers: list[str]
    fecha_inicio: date
    fecha_fin: date
    recolectar: RecolectorResultados


def universo_real(input_folder: Path) -> FuenteUniverso:
    universo = universo_real_csv(input_folder)
    if not universo:
        raise ValueError(
            "No hay CSV históricos guardados en input/ ni input/processed/ "
            "para reconstruir el universo real."
        )
    todos_tickers = sorted({t for tickers in universo.values() for t in tickers})
    fechas = sorted(universo.keys())

    async def _recolectar(config: ScanConfig) -> list[ResultadoDia]:
        return await recolectar_resultados_universo_real(universo, config)

    return FuenteUniverso(
        tickers=todos_tickers,
        fecha_inicio=fechas[0],
        fecha_fin=fechas[-1],
        recolectar=_recolectar,
    )


def universo_curado(tickers: list[str], fecha_inicio: date, fecha_fin: date) -> FuenteUniverso:
    if not tickers:
        raise ValueError("El universo curado necesita al menos un ticker.")
    if fecha_inicio > fecha_fin:
        raise ValueError("fecha_inicio no puede ser posterior a fecha_fin.")

    tickers_ordenados = sorted(set(tickers))

    async def _recolectar(config: ScanConfig) -> list[ResultadoDia]:
        return await recolectar_resultados(tickers_ordenados, fecha_inicio, fecha_fin, config)

    return FuenteUniverso(
        tickers=tickers_ordenados,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        recolectar=_recolectar,
    )
