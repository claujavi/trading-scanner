"""
metrics.py — agrega resultados de un backtest (ScanResult + simulación de
cada señal operable) en un único BacktestRun.

Este módulo calcula ÚNICAMENTE métricas objetivas de la estrategia —  nunca
lógica de ranking, penalización, ni "qué config es mejor que otra". Esa
decisión es responsabilidad exclusiva de optimizer/fitness.py, que consume
EstrategiaMetrics sin que este módulo sepa que existe un optimizador.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from ..models import BacktestRun, Clasificacion, ScanConfig, ScanResult
from .simulator import ResultadoSimulacion

ResultadoDia = tuple[ScanResult, Optional[ResultadoSimulacion]]


@dataclass
class EstrategiaMetrics:
    """Métricas objetivas de una estrategia sobre un conjunto de trades
    simulados, en múltiplos de R (no hay position sizing/capital real
    trackeado en este sistema — ver simulator.py)."""

    total_trades: int
    win_rate: float          # % de trades con resultado_r > 0
    net_profit_r: float      # suma de resultado_r de todos los trades
    expectancy_r: float      # resultado_r promedio por trade
    profit_factor: float     # suma ganancias / abs(suma pérdidas), en R
    avg_win_r: float         # promedio de resultado_r entre trades ganadores
    avg_loss_r: float        # promedio de resultado_r entre trades perdedores (negativo)
    max_drawdown_r: float    # mayor caída pico-a-valle sobre la curva acumulada de R


def _win_rate(simulaciones: list[ResultadoSimulacion]) -> float:
    if not simulaciones:
        return 0.0
    ganadoras = sum(1 for s in simulaciones if s.resultado_r > 0)
    return ganadoras / len(simulaciones) * 100.0


def _rr_promedio(simulaciones: list[ResultadoSimulacion]) -> float:
    if not simulaciones:
        return 0.0
    return sum(s.resultado_r for s in simulaciones) / len(simulaciones)


def _profit_factor(simulaciones: list[ResultadoSimulacion]) -> float:
    ganancias = sum(s.resultado_r for s in simulaciones if s.resultado_r > 0)
    perdidas = abs(sum(s.resultado_r for s in simulaciones if s.resultado_r < 0))
    if perdidas == 0:
        return ganancias if ganancias > 0 else 0.0
    return ganancias / perdidas


def _max_drawdown_r(simulaciones: list[ResultadoSimulacion]) -> float:
    """Drawdown máximo expresado en múltiplos de R acumulados (no % de
    capital — no se trackea position sizing/curva de capital real en este MVP)."""
    if not simulaciones:
        return 0.0
    acumulado = 0.0
    pico = 0.0
    max_dd = 0.0
    for s in simulaciones:
        acumulado += s.resultado_r
        pico = max(pico, acumulado)
        max_dd = max(max_dd, pico - acumulado)
    return max_dd


def calcular_metricas(
    config: ScanConfig,
    fecha_inicio: date,
    fecha_fin: date,
    tickers: list[str],
    resultados: list[ResultadoDia],
) -> BacktestRun:
    total_señales = len(resultados)
    señales_day = sum(1 for r, _ in resultados if r.clasificacion == Clasificacion.DAY)
    señales_swing = sum(1 for r, _ in resultados if r.clasificacion == Clasificacion.SWING)
    señales_ambiguo = sum(1 for r, _ in resultados if r.clasificacion == Clasificacion.AMBIGUO)
    señales_descartadas = sum(1 for r, _ in resultados if r.clasificacion == Clasificacion.DESCARTAR)

    señales_green = sum(1 for r, _ in resultados if r.warning_calendar == "GREEN")
    señales_yellow = sum(1 for r, _ in resultados if r.warning_calendar == "YELLOW")
    señales_red = sum(1 for r, _ in resultados if r.warning_calendar == "RED")

    ops_day = [s for r, s in resultados if r.clasificacion == Clasificacion.DAY and s is not None]
    ops_swing = [s for r, s in resultados if r.clasificacion == Clasificacion.SWING and s is not None]
    ops_todas = ops_day + ops_swing

    return BacktestRun(
        config_snapshot=config.model_dump(mode="json"),
        config_nombre=config.nombre,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tickers=tickers,
        total_señales=total_señales,
        total_operadas=len(ops_todas),
        win_rate_day=_win_rate(ops_day),
        win_rate_swing=_win_rate(ops_swing),
        rr_promedio_real=_rr_promedio(ops_todas),
        rr_promedio_day=_rr_promedio(ops_day),
        rr_promedio_swing=_rr_promedio(ops_swing),
        profit_factor=_profit_factor(ops_todas),
        max_drawdown_pct=_max_drawdown_r(ops_todas),
        señales_day=señales_day,
        señales_swing=señales_swing,
        señales_ambiguo=señales_ambiguo,
        señales_descartadas=señales_descartadas,
        señales_green=señales_green,
        señales_yellow=señales_yellow,
        señales_red=señales_red,
    )


def calcular_metricas_estrategia(simulaciones: list[ResultadoSimulacion]) -> EstrategiaMetrics:
    """Métricas objetivas puras a partir de una lista de trades simulados.

    Pensada para el optimizador: no depende de ScanResult/BacktestRun/config
    ni de fechas/tickers — solo de los resultados de la simulación. Reusa los
    mismos helpers privados que calcular_metricas() para no duplicar lógica.
    """
    ganadores = [s.resultado_r for s in simulaciones if s.resultado_r > 0]
    perdedores = [s.resultado_r for s in simulaciones if s.resultado_r < 0]

    return EstrategiaMetrics(
        total_trades=len(simulaciones),
        win_rate=_win_rate(simulaciones),
        net_profit_r=sum(s.resultado_r for s in simulaciones),
        expectancy_r=_rr_promedio(simulaciones),
        profit_factor=_profit_factor(simulaciones),
        avg_win_r=(sum(ganadores) / len(ganadores)) if ganadores else 0.0,
        avg_loss_r=(sum(perdedores) / len(perdedores)) if perdedores else 0.0,
        max_drawdown_r=_max_drawdown_r(simulaciones),
    )
