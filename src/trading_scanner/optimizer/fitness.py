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
    # Cap para que max_drawdown_r no domine el score con estrategias de alta
    # frecuencia (ej. 3BP/4BP: cientos-miles de trades por corrida, contra
    # las ~15-30 del clasificador de 6 criterios). max_drawdown_r es la
    # única métrica de la fórmula que es una SUMA (caída acumulada sobre
    # toda la serie de trades tratada como una sola curva secuencial), no
    # una tasa/ratio como expectancy_r o profit_factor — con miles de
    # trades esa suma crece sin límite real y ahoga a las demás señales.
    # Hallazgo real (2026-08-06): calibrando 3BP/15m con ~700-2000 trades
    # por trial, drawdown_r llegó a 34.3 sobre el universo completo, dando
    # fitness negativo en los 50 trials y sesgando al optimizador hacia
    # "menos señales" en vez de "mejor señal por trade" (un trial con
    # mejor expectancy perdía contra uno con más drawdown acumulado solo
    # por tener más trades). Default 15.0 generoso a propósito: no debe
    # activarse en el uso normal del clasificador de 6 criterios (donde el
    # drawdown observado hasta ahora nunca superó ~2R), solo entra en
    # juego con volúmenes de trades mucho más altos.
    max_drawdown_tope: float = Field(15.0, gt=0)
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
    drawdown_acotado = min(metrics.max_drawdown_r, config.max_drawdown_tope)
    score_base = (
        config.peso_expectancy * metrics.expectancy_r
        + config.peso_profit_factor * profit_factor_acotado
        - config.peso_drawdown * drawdown_acotado
    )
    return score_base * _factor_confiabilidad(metrics.total_trades, config)
