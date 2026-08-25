"""
metrics_3bp.py — agrega eventos 3BP/4BP (siempre de backtest, ver
walker_3bp.py) en un Bp34BacktestRun. Reusa los helpers de agregación
puros de backtest/metrics.py (_win_rate, _rr_promedio, _profit_factor) —
operan por duck-typing sobre cualquier objeto con `.resultado_r`;
Bp34Evento lo cumple, no hace falta reimplementarlos. Tabla y modelo
separados de metrics.py/BacktestRun (nunca mezclado con el clasificador de
6 criterios), mismo criterio de separación que ya sigue todo el módulo
3BP/4BP.
"""

import asyncio
from datetime import date

from ..logging_setup import console
from ..models import Bp34BacktestRun, Bp34Evento, ResultadoBp34, ScanConfig
from .metrics import _profit_factor, _rr_promedio, _win_rate
from .walker_3bp import caminar_3bp

# Mismo límite y motivo que backtest/runner.py::_SCHWAB_CONCURRENCY — no
# abrir demasiadas conexiones reales a Schwab si el cache está incompleto.
_SCHWAB_CONCURRENCY = asyncio.Semaphore(5)


async def _caminar_con_limite(
    ticker: str, timeframe: str, fecha_inicio: date, fecha_fin: date, config: ScanConfig
) -> list[Bp34Evento]:
    async with _SCHWAB_CONCURRENCY:
        return await caminar_3bp(ticker, timeframe, fecha_inicio, fecha_fin, config)


async def recolectar_eventos_3bp(
    tickers: list[str], timeframe: str, fecha_inicio: date, fecha_fin: date, config: ScanConfig
) -> list[Bp34Evento]:
    """Corre el walker para varios tickers en paralelo (acotado por
    _SCHWAB_CONCURRENCY) y aplana los resultados.

    Ordenado por `timestamp` antes de devolver: cada tarea de `asyncio.gather`
    ya viene en orden cronológico *dentro* de su propio ticker, pero entre
    tickers quedan concatenados en el orden de la lista `tickers` (alfabético
    en la práctica), no por fecha real. Sin este sort, cualquier cálculo que
    trate la lista como una curva de capital secuencial (ver
    `backtest/metrics.py::_max_drawdown_r`, reusada por
    `calcular_metricas_3bp`/`calcular_metricas_estrategia`) recorrería
    primero todo el historial de un ticker y después el del siguiente —una
    "racha perdedora" artificial que ningún trader real experimentaría
    operando 400+ tickers en simultáneo con los trades intercalados por
    calendario. Confirmado en la calibración de 2026-08-24: infló
    max_drawdown_r a 47R sobre 6923 trades, saturando por completo el tope
    de la fórmula de fitness."""
    tareas = [_caminar_con_limite(t, timeframe, fecha_inicio, fecha_fin, config) for t in tickers]
    resultados = await asyncio.gather(*tareas, return_exceptions=True)

    eventos: list[Bp34Evento] = []
    errores = 0
    for item in resultados:
        if isinstance(item, Exception):
            errores += 1
        else:
            eventos.extend(item)
    eventos.sort(key=lambda e: e.timestamp)

    console.log(
        f"[green]Walker 3BP: {len(eventos)} eventos"
        + (f", {errores} tickers con error" if errores else "")
        + "[/green]"
    )
    return eventos


def calcular_metricas_3bp(eventos: list[Bp34Evento]) -> dict:
    """Métricas objetivas puras a partir de una lista de eventos — sin
    lógica de ranking (mismo principio que backtest/metrics.py). El walker
    de backtest siempre resuelve cada entrada (TARGET/STOP/SIN_DEFINIR),
    nunca deja `resultado_r=None` — el filtro de acá es defensivo, pensado
    para cuando esta misma función se reuse con eventos en vivo (`ABIERTO`,
    sin resultado todavía)."""
    resueltos = [e for e in eventos if e.resultado_r is not None]
    confirmados = [e for e in resueltos if e.tier == "confirmado"]
    sin_confirmar = [e for e in resueltos if e.tier == "sin_confirmar"]

    return {
        "total_eventos": len(eventos),
        "total_entradas": len(resueltos),
        "win_rate": _win_rate(resueltos),
        "win_rate_confirmado": _win_rate(confirmados),
        "win_rate_sin_confirmar": _win_rate(sin_confirmar),
        "rr_promedio": _rr_promedio(resueltos),
        "profit_factor": _profit_factor(resueltos),
        "señales_target": sum(1 for e in resueltos if e.resultado == ResultadoBp34.TARGET),
        "señales_stop": sum(1 for e in resueltos if e.resultado == ResultadoBp34.STOP),
        "señales_sin_definir": sum(1 for e in resueltos if e.resultado == ResultadoBp34.SIN_DEFINIR),
    }


async def run_backtest_3bp(
    tickers: list[str], timeframe: str, fecha_inicio: date, fecha_fin: date, config: ScanConfig
) -> Bp34BacktestRun:
    """Backtest completo del módulo 3BP/4BP para un timeframe — corrida
    separada del optimizador de 6 criterios (spec, sección 8). Solo
    persiste el agregado (Bp34BacktestRun) — mismo criterio que ya sigue
    run_backtest() del clasificador de 6 criterios, que tampoco persiste
    cada ScanResult individual de un backtest en scan_results. Los eventos
    individuales de esta corrida quedan en memoria (visibles vía el
    resultado de esta función), no en bp34_eventos — esa tabla hoy solo la
    puebla el vivo (ver main.py::_on_evento_3bp)."""
    eventos = await recolectar_eventos_3bp(tickers, timeframe, fecha_inicio, fecha_fin, config)
    metricas = calcular_metricas_3bp(eventos)
    return Bp34BacktestRun(
        config_snapshot=config.model_dump(mode="json"),
        timeframe=timeframe,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tickers=sorted(set(tickers)),
        **metricas,
    )
