"""
walker_3bp.py — backtest del módulo 3BP/4BP (paso 4 de
docs/spec_modulo_3bp_4bp.md, "Orden de trabajo acordado"). Reusa el mismo
Detector3BP que corre en vivo (fetchers/market_data_cache.py) — un
caminador vela por vela, no el patrón "un día = un contexto" de
backtest/runner.py (incompatible con una máquina de estados intradía, ver
checkpoint del paso 4, ya resuelto).

Replica EXACTAMENTE el reseteo diario que ya usa el vivo
(market_data_cache.py::seed()/_crear_detector_3bp): un Detector3BP nuevo y
un contexto de velas vacío por cada día de trading — nunca hereda contexto
de pre-market ni de días previos (mismo "punto ciego" ya documentado allá:
sin señales posibles en los primeros ~15-45 minutos de sesión según
timeframe). ATR14 y volumen promedio de referencia se calculan sobre la
propia serie del día (no el ATR%/volumen diario que usa el clasificador de
6 criterios) — reusa las mismas funciones privadas que ya usa el stream
(_atr14_de_velas/_volumen_promedio_de_velas/_a_vela_pattern/
_crear_detector_3bp) en vez de reimplementarlas, mismo criterio que ya
aplicó el resto del sistema hoy (ver runner.py/simulator.py).

Una entrada (Estado 3) se sigue con el precio real post-señal DENTRO del
mismo día (3BP es una señal de timing intradía — la spec no define
sostenimiento multi-día para este módulo, a diferencia del SWING del
clasificador de 6 criterios) hasta tocar target, tocar stop, o el cierre
forzado a las 15:55 NY (misma regla que simulator.py, reusada — no
reimplementada).
"""

from datetime import date
from typing import Optional

import polars as pl

from ..engine.pattern_3bp import Estado3BP
from ..fetchers import history_cache
from ..fetchers.market_data_cache import (
    Vela,
    _a_vela_pattern,
    _atr14_de_velas,
    _crear_detector_3bp,
    _volumen_promedio_de_velas,
)
from ..logging_setup import console
from ..models import Bp34Evento, FuenteDatos, ResultadoBp34, ScanConfig
from .runner import _dias_habiles
from .simulator import _truncar_a_cierre_forzado

_MINUTOS_POR_TIMEFRAME = {"5m": 5, "15m": 15}


def _df_a_velas(df: pl.DataFrame) -> list[Vela]:
    if df.is_empty():
        return []
    return [
        Vela(
            timestamp=row["timestamp"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )
        for row in df.sort("timestamp").iter_rows(named=True)
    ]


def _resolver_entrada(
    velas_desde_gatillo: list[Vela],
    entry: float,
    stop: float,
    target_r: float,
    timeframe: str,
) -> tuple[ResultadoBp34, float, float, float, int]:
    """`velas_desde_gatillo` incluye la barra gatillo (índice 0, la que
    disparó ENTRADA) y todo lo que sigue en el día, ya truncado al cierre
    forzado. La barra gatillo se revisa también por target/stop — el
    breakout que dispara la entrada puede, en esa misma barra, seguir
    moviéndose hasta el target o revertir hasta el stop, y con solo OHLC
    no hay forma de saber el orden real intra-barra. Mismo criterio
    pesimista que simulator.py::_fixed_rr: si una barra toca ambos, gana
    el stop. Devuelve (resultado, resultado_r, mfe_r, mae_r,
    tiempo_en_trade_minutos)."""
    stop_dist = entry - stop
    if not velas_desde_gatillo or stop_dist <= 0:
        return ResultadoBp34.SIN_DEFINIR, 0.0, 0.0, 0.0, 0

    target = entry + stop_dist * target_r
    minutos_vela = _MINUTOS_POR_TIMEFRAME[timeframe]

    mfe_r = 0.0
    mae_r = 0.0
    for i, vela in enumerate(velas_desde_gatillo):
        mfe_r = max(mfe_r, (vela.high - entry) / stop_dist)
        mae_r = min(mae_r, (vela.low - entry) / stop_dist)
        if vela.low <= stop:
            return ResultadoBp34.STOP, -1.0, mfe_r, mae_r, i * minutos_vela
        if vela.high >= target:
            return ResultadoBp34.TARGET, target_r, mfe_r, mae_r, i * minutos_vela

    cierre = velas_desde_gatillo[-1].close
    resultado_r = (cierre - entry) / stop_dist
    tiempo = (len(velas_desde_gatillo) - 1) * minutos_vela
    return ResultadoBp34.SIN_DEFINIR, resultado_r, mfe_r, mae_r, tiempo


def _caminar_dia(
    velas_dia: list[Vela],
    ticker: str,
    timeframe: str,
    fecha: date,
    config: ScanConfig,
    fuente: FuenteDatos,
) -> list[Bp34Evento]:
    """Camina un día de un ticker+timeframe: detector fresco, contexto
    vacío — mismo reseteo diario que ya hace seed() en vivo. Un mismo día
    puede producir varias entradas independientes (el detector vuelve a
    SIN_PATRON apenas emite ENTRADA, ver pattern_3bp.py::procesar_barra)."""
    detector = _crear_detector_3bp(config, timeframe)
    target_r = getattr(config, f"bp34_target_r_{timeframe}")
    config_snapshot = config.model_dump(mode="json")

    eventos: list[Bp34Evento] = []
    for i, vela in enumerate(velas_dia):
        contexto = velas_dia[: i + 1]
        atr14 = _atr14_de_velas(contexto)
        if atr14 is None:
            continue  # todavía no hay suficiente contexto de sesión — mismo criterio que en vivo
        volumen_promedio = _volumen_promedio_de_velas(contexto)

        evento = detector.procesar_barra(_a_vela_pattern(vela), atr14, volumen_promedio)
        if evento is None or evento.estado != Estado3BP.ENTRADA:
            continue

        resultado, resultado_r, mfe_r, mae_r, tiempo = _resolver_entrada(
            velas_dia[i:], evento.entry, evento.stop, target_r, timeframe
        )
        eventos.append(Bp34Evento(
            ticker=ticker,
            timeframe=timeframe,
            fecha=fecha,
            timestamp=vela.timestamp,
            fuente=fuente,
            tipo=evento.tipo,
            tier=evento.tier,
            entry=evento.entry,
            stop=evento.stop,
            target=evento.entry + (evento.entry - evento.stop) * target_r,
            resultado=resultado,
            resultado_r=resultado_r,
            mfe_r=mfe_r,
            mae_r=mae_r,
            tiempo_en_trade_minutos=tiempo,
            config_snapshot=config_snapshot,
        ))
    return eventos


async def caminar_3bp(
    ticker: str, timeframe: str, fecha_inicio: date, fecha_fin: date, config: ScanConfig
) -> list[Bp34Evento]:
    """Backtest del módulo 3BP/4BP para un ticker+timeframe — un
    Detector3BP fresco por día, reusando el mismo motor que corre en vivo.
    `timeframe`: "5m" | "15m" — perfiles independientes, nunca mezclados
    (spec, sección 1)."""
    piso_intraday = history_cache.FECHA_INICIO_DEFAULT[timeframe]
    if fecha_fin < piso_intraday:
        return []  # Schwab no tiene intradía tan atrás, ver CLAUDE.md
    fecha_inicio_efectiva = max(fecha_inicio, piso_intraday)

    try:
        df_full = await history_cache.get_history(ticker, timeframe, fecha_inicio_efectiva, fecha_fin)
    except Exception as exc:
        console.log(f"[yellow]Walker 3BP: sin historial de {ticker} ({timeframe}): {exc}[/yellow]")
        return []

    if df_full.is_empty():
        return []

    eventos: list[Bp34Evento] = []
    for dia in _dias_habiles(fecha_inicio_efectiva, fecha_fin):
        df_dia = history_cache.filter_range(df_full, dia, dia)
        df_dia = _truncar_a_cierre_forzado(df_dia)
        if df_dia.is_empty():
            continue
        velas_dia = _df_a_velas(df_dia)
        eventos.extend(_caminar_dia(velas_dia, ticker, timeframe, dia, config, FuenteDatos.HISTORICO))
    return eventos
