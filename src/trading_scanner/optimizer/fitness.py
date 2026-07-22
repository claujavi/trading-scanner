"""
fitness.py — única pieza del optimizador con lógica de "qué trial es mejor
que otro". Deliberadamente separado de backtest/metrics.py: ese módulo solo
calcula métricas objetivas de la estrategia (EstrategiaMetrics), nunca
ranking ni penalizaciones. Cambiar la fórmula de fitness (pesos, curva de
penalización, qué métricas entran) se hace acá sin tocar metrics.py ni el
backtest.

Penalización por cantidad de trades: gradual (sigmoide), no un corte duro.
Una config con pocos trades no se descarta de plano — compite en desventaja
creciente cuanto más lejos esté de `trades_objetivo`, evitando que el
optimizador converja en configs demasiado restrictivas con 2-3 señales en
todo el período, pero sin la fragilidad de un umbral fijo tipo "if < 30: 0".
"""

import math

from pydantic import BaseModel, Field

from ..backtest.metrics import EstrategiaMetrics


class FitnessConfig(BaseModel):
    """Parámetros de la fórmula de fitness. No es ScanConfig — esto no
    describe la estrategia de trading, describe cómo el optimizador puntúa
    los resultados de esa estrategia."""

    peso_expectancy: float = Field(1.0, ge=0)
    peso_profit_factor: float = Field(0.5, ge=0)
    peso_drawdown: float = Field(1.0, ge=0)
    profit_factor_tope: float = Field(5.0, gt=0)  # cap para no sobreponderar outliers con pocos trades
    trades_objetivo: int = Field(30, gt=0)  # a partir de acá, el factor de confiabilidad ronda 1.0
    pendiente_penalizacion: float = Field(0.15, gt=0)  # qué tan abrupta es la curva por debajo del objetivo


def _factor_confiabilidad(total_trades: int, config: FitnessConfig) -> float:
    """Sigmoide en [0, 1) centrada en trades_objetivo. Penaliza gradualmente
    trials con pocos trades sin descartarlos con un corte duro."""
    x = (total_trades - config.trades_objetivo) * config.pendiente_penalizacion
    return 1.0 / (1.0 + math.exp(-x))


def calcular_fitness(metrics: EstrategiaMetrics, config: FitnessConfig = FitnessConfig()) -> float:
    """Score único que Optuna maximiza. Combina expectancy y profit factor
    (las métricas que mejor capturan rentabilidad sostenida por trade),
    penalizadas por drawdown y escaladas por confiabilidad estadística
    según la cantidad de trades."""
    if metrics.total_trades == 0:
        return -math.inf

    profit_factor_acotado = min(metrics.profit_factor, config.profit_factor_tope)
    score_base = (
        config.peso_expectancy * metrics.expectancy_r
        + config.peso_profit_factor * profit_factor_acotado
        - config.peso_drawdown * metrics.max_drawdown_r
    )
    return score_base * _factor_confiabilidad(metrics.total_trades, config)
