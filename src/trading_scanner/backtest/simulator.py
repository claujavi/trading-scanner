"""
simulator.py — simula el resultado de una señal según el modo de salida
configurado (ScanConfig.modo_salida), usando velas intradía (5m) del
mismo día de la señal.

Asume operaciones LONG-ONLY. El resto del sistema está orientado a comprar
fuerza/momentum (ivr_umbral_compra habla de "opciones baratas para comprar",
no hay lógica de venta en corto en ningún otro lado) — no se simula short.

"Primera resistencia" en PARTIAL_SCALE es una simplificación deliberada: no
hay detección de soportes/resistencias técnicas en el proyecto (indicators/
no la calcula), así que se usa el mismo target de ATR que FIXED_RR
(`target_atr_multiplicador`) como proxy.
"""

from dataclasses import dataclass
from typing import Optional

import polars as pl

from ..models import ModoSalida, ScanConfig


@dataclass
class ResultadoSimulacion:
    precio_entrada: float
    precio_salida: float
    resultado_r: float  # múltiplos de R (positivo = ganancia, negativo = pérdida)
    motivo_salida: str  # "target" | "stop" | "eod" | "parcial+trailing"


def _slippage(precio: float, config: ScanConfig, es_entrada: bool) -> float:
    ajuste = precio * (config.slippage_bps / 10_000)
    return precio + ajuste if es_entrada else precio - ajuste


def simular(velas_dia: pl.DataFrame, atr: float, config: ScanConfig) -> Optional[ResultadoSimulacion]:
    """velas_dia: velas de 5m del día de la señal, ordenadas por timestamp,
    empezando desde la vela de entrada (la primera vela de la sesión)."""
    if velas_dia is None or velas_dia.is_empty() or atr is None or atr <= 0:
        return None

    if config.modo_salida == ModoSalida.FIXED_RR:
        return _fixed_rr(velas_dia, atr, config)
    if config.modo_salida == ModoSalida.TRAILING_EOD:
        return _trailing_eod(velas_dia, atr, config)
    return _partial_scale(velas_dia, atr, config)


def _fixed_rr(velas: pl.DataFrame, atr: float, config: ScanConfig) -> Optional[ResultadoSimulacion]:
    entrada = _slippage(float(velas["open"][0]), config, es_entrada=True)
    stop_dist = atr * config.stop_atr_multiplicador
    if stop_dist <= 0:
        return None
    stop = entrada - stop_dist
    target = entrada + stop_dist * config.rr_target

    for row in velas.iter_rows(named=True):
        low, high = float(row["low"]), float(row["high"])
        if low <= stop:
            salida = _slippage(stop, config, es_entrada=False)
            return ResultadoSimulacion(entrada, salida, -1.0, "stop")
        if high >= target:
            salida = _slippage(target, config, es_entrada=False)
            return ResultadoSimulacion(entrada, salida, config.rr_target, "target")

    cierre = _slippage(float(velas["close"][-1]), config, es_entrada=False)
    r = (cierre - entrada) / stop_dist
    return ResultadoSimulacion(entrada, cierre, r, "eod")


def _trailing_eod(velas: pl.DataFrame, atr: float, config: ScanConfig) -> Optional[ResultadoSimulacion]:
    entrada = _slippage(float(velas["open"][0]), config, es_entrada=True)
    stop_dist = atr * config.stop_atr_multiplicador
    if stop_dist <= 0:
        return None
    stop = entrada - stop_dist
    max_precio = entrada

    for row in velas.iter_rows(named=True):
        low, high = float(row["low"]), float(row["high"])
        if low <= stop:
            salida = _slippage(stop, config, es_entrada=False)
            r = (salida - entrada) / stop_dist
            return ResultadoSimulacion(entrada, salida, r, "stop")

        if high > max_precio:
            max_precio = high
            ganancia_r = (max_precio - entrada) / stop_dist
            if ganancia_r >= config.trailing_lock_r:
                stop = max(stop, entrada + stop_dist * (config.trailing_lock_r - 1.0))
            elif ganancia_r >= config.trailing_activacion_r:
                stop = max(stop, entrada)  # mover a breakeven

    cierre = _slippage(float(velas["close"][-1]), config, es_entrada=False)
    r = (cierre - entrada) / stop_dist
    return ResultadoSimulacion(entrada, cierre, r, "eod")


def _partial_scale(velas: pl.DataFrame, atr: float, config: ScanConfig) -> Optional[ResultadoSimulacion]:
    entrada = _slippage(float(velas["open"][0]), config, es_entrada=True)
    stop_dist = atr * config.stop_atr_multiplicador
    if stop_dist <= 0:
        return None
    stop = entrada - stop_dist
    primera_resistencia = entrada + stop_dist * (
        config.target_atr_multiplicador / config.stop_atr_multiplicador
    )

    mitad_vendida = False
    r_mitad1 = 0.0
    max_precio = entrada
    stop_resto = stop

    for row in velas.iter_rows(named=True):
        low, high = float(row["low"]), float(row["high"])

        if not mitad_vendida:
            if low <= stop:
                salida = _slippage(stop, config, es_entrada=False)
                r = (salida - entrada) / stop_dist
                return ResultadoSimulacion(entrada, salida, r, "stop")
            if high >= primera_resistencia:
                r_mitad1 = (primera_resistencia - entrada) / stop_dist
                mitad_vendida = True
                stop_resto = entrada  # breakeven para el resto tras asegurar la 1ra mitad
                max_precio = high
            continue

        if low <= stop_resto:
            r2 = (stop_resto - entrada) / stop_dist
            salida = _slippage(stop_resto, config, es_entrada=False)
            return ResultadoSimulacion(entrada, salida, (r_mitad1 + r2) / 2.0, "parcial+trailing")
        if high > max_precio:
            max_precio = high
            ganancia_r = (max_precio - entrada) / stop_dist
            if ganancia_r >= config.trailing_lock_r:
                stop_resto = max(stop_resto, entrada + stop_dist * (config.trailing_lock_r - 1.0))

    cierre = float(velas["close"][-1])
    salida = _slippage(cierre, config, es_entrada=False)
    if not mitad_vendida:
        r = (salida - entrada) / stop_dist
        return ResultadoSimulacion(entrada, salida, r, "eod")

    r2 = (cierre - entrada) / stop_dist
    return ResultadoSimulacion(entrada, salida, (r_mitad1 + r2) / 2.0, "parcial+trailing")
