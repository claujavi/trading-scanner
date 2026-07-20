from typing import Optional, Tuple

from ..models import ScanConfig


def criterio_timeframe_setup(
    cruce_5m: Optional[bool],
    cruce_15m: Optional[bool],
    cruce_4h: Optional[bool],
    cruce_d: Optional[bool],
) -> Optional[Tuple[float, float]]:
    """Evalúa la señal de setup en múltiples timeframes."""
    if None in (cruce_5m, cruce_15m, cruce_4h, cruce_d):
        return None

    bullish_signals = sum([cruce_5m, cruce_15m, cruce_4h, cruce_d])
    bearish_signals = 4 - bullish_signals

    score_day = bullish_signals / 4.0
    score_swing = bearish_signals / 4.0
    return score_day, score_swing


def criterio_catalizador(
    catalizador_detectado: Optional[bool],
    warning_level: Optional[str],
) -> Optional[Tuple[float, float]]:
    if catalizador_detectado is None or warning_level is None:
        return None

    if not catalizador_detectado:
        return 1.0, 1.0

    warning = warning_level.upper()
    if warning == "RED":
        return 0.2, 0.2
    if warning == "YELLOW":
        return 0.6, 0.6
    return 1.0, 1.0


def criterio_relvol(relvol: Optional[float], config: ScanConfig) -> Optional[Tuple[float, float]]:
    if relvol is None:
        return None

    if relvol >= config.relvol_umbral_day:
        return 1.0, 0.0
    if config.relvol_umbral_swing_min <= relvol < config.relvol_umbral_swing_max:
        return 0.0, 1.0
    return 0.0, 0.0


def criterio_atr_pct(atr_pct: Optional[float], config: ScanConfig) -> Optional[Tuple[float, float]]:
    if atr_pct is None:
        return None

    if atr_pct >= config.atr_pct_umbral_day:
        return 1.0, 0.0
    if config.atr_pct_umbral_swing_min <= atr_pct < config.atr_pct_umbral_swing_max:
        return 0.0, 1.0
    return 0.0, 0.0


def criterio_sma200(sobre_sma200: Optional[bool]) -> Optional[Tuple[float, float]]:
    if sobre_sma200 is None:
        return None
    return (1.0, 0.0) if sobre_sma200 else (0.0, 1.0)


def criterio_ivr(ivr: Optional[float], config: ScanConfig) -> Optional[Tuple[float, float]]:
    if ivr is None:
        return None

    if ivr < config.ivr_umbral_compra:
        return 1.0, 0.0
    if ivr > config.ivr_umbral_venta:
        return 0.0, 1.0
    return 1.0, 1.0
