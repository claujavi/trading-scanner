from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from ..models import ScanConfig, ScanResult, Clasificacion, FuenteDatos
from .criteria import (
    criterio_atr_pct,
    criterio_capital,
    criterio_catalizador,
    criterio_ivr,
    criterio_relvol,
    criterio_sma200,
    criterio_timeframe_setup,
)


@dataclass(frozen=True)
class DatosTickerCompletos:
    ticker: str
    fecha: date
    timestamp: datetime
    fuente: FuenteDatos
    precio: float
    variacion_diaria_pct: float
    relvol: Optional[float]
    atr_pct: Optional[float]
    volumen_actual: int
    sobre_sma200: Optional[bool]
    sobre_ema50: Optional[bool]
    cruce_ema_921_5m: Optional[bool]
    cruce_ema_921_15m: Optional[bool]
    cruce_ema_921_4h: Optional[bool]
    cruce_ema_921_d: Optional[bool]
    ivr: Optional[float]
    warning_calendar: Optional[str]
    earnings_24h: bool
    evento_macro_24h: bool
    filing_8k_24h: bool
    upgrade_downgrade_24h: bool
    catalizador_detectado: bool
    volumen_promedio: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None


_CRITERIO_NOMBRES = [
    "timeframe_setup",
    "catalizador",
    "relvol",
    "atr_pct",
    "sma200",
    "ivr",
    "capital",
]

_PESOS_ATTRS = [
    "peso_timeframe_setup",
    "peso_catalizador",
    "peso_relvol",
    "peso_atr_pct",
    "peso_sma200",
    "peso_ivr",
    "peso_capital",
]


def _normalizar_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def _clasificar(score_day: float, score_swing: float, config: ScanConfig) -> Clasificacion:
    if score_day >= config.umbral_decision and score_day > score_swing:
        return Clasificacion.DAY
    if score_swing >= config.umbral_decision and score_swing > score_day:
        return Clasificacion.SWING
    if score_day >= config.umbral_decision and score_swing >= config.umbral_decision:
        return Clasificacion.AMBIGUO
    return Clasificacion.DESCARTAR


def _build_result(datos: DatosTickerCompletos, config: ScanConfig, **kwargs) -> ScanResult:
    return ScanResult(
        ticker=datos.ticker,
        fecha=datos.fecha,
        timestamp=datos.timestamp,
        fuente=datos.fuente,
        config_snapshot=config.model_dump(mode="json"),
        precio=datos.precio,
        variacion_diaria_pct=datos.variacion_diaria_pct,
        relvol=datos.relvol or 0.0,
        atr_pct=datos.atr_pct or 0.0,
        volumen_actual=datos.volumen_actual,
        sobre_sma200=datos.sobre_sma200,
        sobre_ema50=datos.sobre_ema50,
        cruce_ema_921_5m=datos.cruce_ema_921_5m,
        cruce_ema_921_15m=datos.cruce_ema_921_15m,
        cruce_ema_921_4h=datos.cruce_ema_921_4h,
        cruce_ema_921_d=datos.cruce_ema_921_d,
        rsi_14_5m=None,
        rsi_14_d=None,
        macd_cruce_alcista_15m=None,
        macd_cruce_alcista_d=None,
        ivr=datos.ivr,
        ivr_señal_day=None,
        ivr_señal_swing=None,
        warning_calendar=datos.warning_calendar,
        earnings_24h=datos.earnings_24h,
        evento_macro_24h=datos.evento_macro_24h,
        filing_8k_24h=datos.filing_8k_24h,
        upgrade_downgrade_24h=datos.upgrade_downgrade_24h,
        catalizador_detectado=datos.catalizador_detectado,
        stop_loss_sugerido=None,
        target_sugerido=None,
        rr_calculado=None,
        **kwargs,
    )


def _validar_filtros_entrada(datos: DatosTickerCompletos, config: ScanConfig) -> list[str]:
    """Filtros de entrada (ScanConfig): validan que el ticker sea
    mínimamente operable antes de gastar los 7 criterios en él.

    Distinto de un criterio incompleto — acá se descarta directamente. Si
    un dato no está disponible (ej. sin bid/ask en el CSV), ese filtro
    puntual simplemente no se evalúa, no bloquea por ausencia de dato.
    """
    violaciones = []

    if not (config.precio_min <= datos.precio <= config.precio_max):
        violaciones.append("precio")

    if abs(datos.variacion_diaria_pct) < config.variacion_diaria_min_pct:
        violaciones.append("variacion_diaria")

    if datos.atr_pct is not None and datos.atr_pct < config.atr_pct_min:
        violaciones.append("atr_pct")

    if datos.relvol is not None and datos.relvol < config.relvol_min:
        violaciones.append("relvol")

    if datos.volumen_promedio is not None and datos.volumen_promedio < config.volumen_promedio_min:
        violaciones.append("volumen_promedio")

    if datos.bid is not None and datos.ask is not None and datos.precio > 0:
        spread_pct = (datos.ask - datos.bid) / datos.precio * 100
        if spread_pct > config.spread_max_pct:
            violaciones.append("spread")

    return violaciones


def evaluar(datos: DatosTickerCompletos, config: ScanConfig) -> ScanResult:
    violaciones = _validar_filtros_entrada(datos, config)
    if violaciones:
        return _build_result(
            datos,
            config,
            score_day=0.0,
            score_swing=0.0,
            score_max_posible=0.0,
            clasificacion=Clasificacion.DESCARTAR,
            confianza=0.0,
            criterios_incompletos=[f"FILTRO_ENTRADA:{v}" for v in violaciones],
        )

    resultados = [
        criterio_timeframe_setup(
            datos.cruce_ema_921_5m,
            datos.cruce_ema_921_15m,
            datos.cruce_ema_921_4h,
            datos.cruce_ema_921_d,
        ),
        criterio_catalizador(datos.catalizador_detectado, datos.warning_calendar),
        criterio_relvol(datos.relvol, config),
        criterio_atr_pct(datos.atr_pct, config),
        criterio_sma200(datos.sobre_sma200),
        criterio_ivr(datos.ivr, config),
        criterio_capital(config),
    ]

    criterios_incompletos = [n for r, n in zip(resultados, _CRITERIO_NOMBRES) if r is None]
    criterios_calculados = len(resultados) - len(criterios_incompletos)

    if criterios_calculados < config.min_criterios_calculables:
        return _build_result(
            datos,
            config,
            score_day=0.0,
            score_swing=0.0,
            score_max_posible=0.0,
            clasificacion=Clasificacion.DESCARTAR,
            confianza=0.0,
            criterios_incompletos=criterios_incompletos + ["INSUFICIENTE_DATA"],
        )

    score_day = 0.0
    score_swing = 0.0
    score_max = 0.0
    for result, attr in zip(resultados, _PESOS_ATTRS):
        if result is None:
            continue
        peso = getattr(config, attr)
        day, swing = result
        score_day += day * peso
        score_swing += swing * peso
        score_max += peso

    winner_score = max(score_day, score_swing)
    confianza = winner_score / score_max if score_max > 0 else 0.0

    return _build_result(
        datos,
        config,
        score_day=score_day,
        score_swing=score_swing,
        score_max_posible=score_max,
        clasificacion=_clasificar(score_day, score_swing, config),
        confianza=_normalizar_score(confianza),
        criterios_incompletos=criterios_incompletos,
    )


def desglosar_criterios(result: ScanResult) -> list[dict]:
    """Recalcula cada criterio individualmente a partir de un ScanResult ya
    persistido, usando su config_snapshot — para auditar visualmente por
    qué dio la clasificación que dio, sin duplicar la lista de criterios
    de evaluar() en otro lugar (misma fuente de verdad)."""
    config = ScanConfig(**result.config_snapshot)

    resultados = [
        criterio_timeframe_setup(
            result.cruce_ema_921_5m,
            result.cruce_ema_921_15m,
            result.cruce_ema_921_4h,
            result.cruce_ema_921_d,
        ),
        criterio_catalizador(result.catalizador_detectado, result.warning_calendar),
        criterio_relvol(result.relvol, config),
        criterio_atr_pct(result.atr_pct, config),
        criterio_sma200(result.sobre_sma200),
        criterio_ivr(result.ivr, config),
        criterio_capital(config),
    ]

    desglose = []
    for nombre, peso_attr, resultado in zip(_CRITERIO_NOMBRES, _PESOS_ATTRS, resultados):
        peso = getattr(config, peso_attr)
        if resultado is None:
            desglose.append({
                "nombre": nombre, "peso": peso, "incompleto": True,
                "score_day": None, "score_swing": None,
            })
        else:
            day, swing = resultado
            desglose.append({
                "nombre": nombre, "peso": peso, "incompleto": False,
                "score_day": day, "score_swing": swing,
            })
    return desglose
