"""
metrics.py — agrega resultados de un backtest (ScanResult + simulación de
cada señal operable) en un único BacktestRun.
"""

from datetime import date
from typing import Optional

from ..models import BacktestRun, Clasificacion, ScanConfig, ScanResult
from .simulator import ResultadoSimulacion

ResultadoDia = tuple[ScanResult, Optional[ResultadoSimulacion]]


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
