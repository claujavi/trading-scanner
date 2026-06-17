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


def _normalizar_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def _sum_scores(
    scores: list[Optional[tuple[float, float]]],
    config: ScanConfig,
    criterion_names: list[str],
) -> tuple[float, float, float, list[str], int]:
    score_day = 0.0
    score_swing = 0.0
    score_max = 0.0
    criterios_incompletos: list[str] = []
    criterios_calculados = 0

    pesos = [
        config.peso_timeframe_setup,
        config.peso_catalizador,
        config.peso_relvol,
        config.peso_atr_pct,
        config.peso_sma200,
        config.peso_ivr,
        config.peso_capital,
    ]

    for result, peso, nombre in zip(scores, pesos, criterion_names):
        if result is None:
            criterios_incompletos.append(nombre)
            continue

        day, swing = result
        criterios_calculados += 1
        score_day += day * peso
        score_swing += swing * peso
        score_max += peso

    return score_day, score_swing, score_max, criterios_incompletos, criterios_calculados


def _clasificar(score_day: float, score_swing: float, config: ScanConfig) -> Clasificacion:
    if score_day >= config.umbral_decision and score_day > score_swing:
        return Clasificacion.DAY
    if score_swing >= config.umbral_decision and score_swing > score_day:
        return Clasificacion.SWING
    if score_day >= config.umbral_decision and score_swing >= config.umbral_decision:
        return Clasificacion.AMBIGUO
    return Clasificacion.DESCARTAR


def evaluar(datos: DatosTickerCompletos, config: ScanConfig) -> ScanResult:
    criterio_nombres = [
        "timeframe_setup",
        "catalizador",
        "relvol",
        "atr_pct",
        "sma200",
        "ivr",
        "capital",
    ]

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

    score_day, score_swing, score_max, criterios_incompletos, criterios_calculados = _sum_scores(
        resultados,
        config,
        criterio_nombres,
    )

    if criterios_calculados < config.min_criterios_calculables:
        criterios_incompletos.append("INSUFICIENTE_DATA")
        return ScanResult(
            ticker=datos.ticker,
            fecha=datos.fecha,
            timestamp=datos.timestamp,
            fuente=datos.fuente,
            config_snapshot=config.model_dump(),
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
            score_day=0.0,
            score_swing=0.0,
            score_max_posible=0.0,
            clasificacion=Clasificacion.DESCARTAR,
            confianza=0.0,
            criterios_incompletos=criterios_incompletos,
            stop_loss_sugerido=None,
            target_sugerido=None,
            rr_calculado=None,
        )

    winner_score = max(score_day, score_swing)
    confianza = winner_score / score_max if score_max > 0 else 0.0

    clasificacion = _clasificar(score_day, score_swing, config)

    return ScanResult(
        ticker=datos.ticker,
        fecha=datos.fecha,
        timestamp=datos.timestamp,
        fuente=datos.fuente,
        config_snapshot=config.model_dump(),
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
        score_day=score_day,
        score_swing=score_swing,
        score_max_posible=score_max,
        clasificacion=clasificacion,
        confianza=_normalizar_score(confianza),
        criterios_incompletos=criterios_incompletos,
        stop_loss_sugerido=None,
        target_sugerido=None,
        rr_calculado=None,
    )
