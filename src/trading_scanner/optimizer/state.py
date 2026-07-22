"""
state.py — progreso del optimizador corriendo en background, en memoria.

No persiste a Turso (eso lo hace study.py/cli.py/api/optimize.py al final,
guardando solo la config ganadora + un BacktestRun) — esto es únicamente
para que el frontend pueda hacer polling del progreso de un run en curso,
igual que market_data_cache.py mantiene el estado del stream en memoria.
Un solo run a la vez: correr el optimizador es una operación manual,
puntual, no concurrente (ver CLAUDE.md: "no correr el optimizador en
producción").
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from ..backtest.metrics import EstrategiaMetrics

if TYPE_CHECKING:
    from .study import OptimizerResultado
    from .universo import FuenteUniverso


@dataclass
class OptimizerEstado:
    corriendo: bool = False
    trial_actual: int = 0
    n_trials: int = 0
    mejor_fitness: Optional[float] = None
    mejor_metrics: Optional[EstrategiaMetrics] = None
    resultado_final: Optional["OptimizerResultado"] = None
    # Fuente de universo usada en este run — necesaria en /optimize/guardar
    # para recolectar los resultados finales con la misma config/universo
    # sin que api/optimize.py tenga que recordarlo por su cuenta.
    fuente: Optional["FuenteUniverso"] = None
    error: Optional[str] = None
    guardado: bool = False


_estado = OptimizerEstado()


def get_estado() -> OptimizerEstado:
    return _estado


def reset_estado(n_trials: int) -> OptimizerEstado:
    global _estado
    _estado = OptimizerEstado(corriendo=True, n_trials=n_trials)
    return _estado
