"""
study.py — orquesta la búsqueda de Optuna sobre el universo real de backtest.

Usa la API ask/tell de Optuna (en vez de study.optimize con un callback
síncrono) para integrarse limpio con el event loop async ya existente en el
proyecto — cada trial corre recolectar_resultados_universo_real(), que es
una corrutina.

No se persiste cada trial en Turso: Optuna corre en memoria durante todo el
comando (ver optimizer/cli.py). Al final, correr_optimizacion() reconstruye
la config ganadora y corre el backtest completo una vez más para producir un
BacktestRun persistible con la infraestructura ya existente (calcular_metricas
+ db.insert_backtest_run), sin duplicar esa lógica acá.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import optuna
from pydantic import ValidationError
from rich.console import Console

from ..backtest.metrics import EstrategiaMetrics, calcular_metricas, calcular_metricas_estrategia
from ..backtest.runner import recolectar_resultados_universo_real, universo_real_csv
from ..models import BacktestRun, ScanConfig
from .fitness import FitnessConfig, calcular_fitness
from .search_space import sugerir_config

# (trial_num, fitness, metrics) — llamado después de cada trial. No sabe nada
# de Turso ni de HTTP: quien lo pasa (api/optimize.py) decide qué hacer con
# el progreso (ej. actualizar optimizer/state.py para que el frontend haga
# polling). El CLI no lo usa — imprime su propio log por Rich dentro del loop.
OnTrialCallback = Callable[[int, float, EstrategiaMetrics], None]

console = Console()

optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass
class OptimizerResultado:
    mejor_config: ScanConfig
    mejor_metrics: EstrategiaMetrics
    mejor_fitness: float
    n_trials: int
    n_trials_validos: int


async def optimizar(
    config_base: ScanConfig,
    input_folder: Path,
    n_trials: int,
    fitness_config: FitnessConfig,
    on_trial: Optional[OnTrialCallback] = None,
) -> OptimizerResultado:
    universo = universo_real_csv(input_folder)
    if not universo:
        raise ValueError(
            "No hay CSV históricos guardados en input/ ni input/processed/ "
            "para reconstruir el universo real."
        )

    study = optuna.create_study(direction="maximize")
    n_validos = 0

    for i in range(n_trials):
        trial = study.ask()
        try:
            config = sugerir_config(trial, config_base)
        except ValidationError as exc:
            study.tell(trial, state=optuna.trial.TrialState.FAIL)
            console.log(f"[yellow]Trial {i}: config inválida descartada ({exc})[/yellow]")
            continue

        resultados = await recolectar_resultados_universo_real(universo, config)
        simulaciones = [s for _, s in resultados if s is not None]
        metrics = calcular_metricas_estrategia(simulaciones)
        fitness = calcular_fitness(metrics, fitness_config)

        trial.set_user_attr("metrics", metrics.__dict__)
        study.tell(trial, fitness)
        n_validos += 1

        console.log(
            f"[cyan]Trial {i+1}/{n_trials}[/cyan] fitness={fitness:.4f} "
            f"trades={metrics.total_trades} expectancy_r={metrics.expectancy_r:.3f}"
        )
        if on_trial:
            on_trial(i + 1, fitness, metrics)

    mejor = study.best_trial
    mejor_config = sugerir_config(optuna.trial.FixedTrial(mejor.params), config_base)
    mejor_metrics = EstrategiaMetrics(**mejor.user_attrs["metrics"])

    return OptimizerResultado(
        mejor_config=mejor_config,
        mejor_metrics=mejor_metrics,
        mejor_fitness=mejor.value,
        n_trials=n_trials,
        n_trials_validos=n_validos,
    )


async def construir_backtest_run_final(mejor_config: ScanConfig, input_folder: Path) -> BacktestRun:
    """Corre un backtest completo (no un trial recortado) de la config
    ganadora para producir un BacktestRun persistible. Compartido por
    optimizer/cli.py y api/optimize.py para no duplicar esta lógica en los
    dos puntos de entrada (CLI y web) que guardan el resultado."""
    universo = universo_real_csv(input_folder)
    resultados = await recolectar_resultados_universo_real(universo, mejor_config)
    todos_tickers = sorted({t for tickers in universo.values() for t in tickers})
    fechas = sorted(universo.keys())
    return calcular_metricas(mejor_config, fechas[0], fechas[-1], todos_tickers, resultados)
