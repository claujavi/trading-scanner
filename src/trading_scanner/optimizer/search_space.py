"""
search_space.py — traduce un trial de Optuna a un ScanConfig completo.

Por regla de CLAUDE.md (ver "DECISIONES DE IMPLEMENTACIÓN NO NEGOCIABLES"), la
primera fase del optimizador deja todos los peso_* fijos en 1.0 y solo busca
sobre umbrales de decisión, rr_target, stop_atr_multiplicador y slippage_bps
— optimizar pesos abre un espacio de búsqueda enorme que sobreajusta con los
datos históricos disponibles hoy.

Los pares min/max (relvol_umbral_swing_*, atr_pct_umbral_swing_*,
ivr_umbral_compra/venta) se samplean con dependencia directa (el "max" se
samplea en un rango que arranca después del "min" ya elegido) para que Optuna
nunca genere una combinación que ScanConfig rechace por sus validators.
"""

import optuna

from ..models import ScanConfig


def sugerir_config(trial: optuna.Trial, config_base: ScanConfig) -> ScanConfig:
    """Construye un ScanConfig para este trial, partiendo de config_base y
    sobreescribiendo solo los campos habilitados para optimización."""
    relvol_umbral_swing_min = trial.suggest_float("relvol_umbral_swing_min", 1.0, 3.0)
    relvol_umbral_swing_max = trial.suggest_float(
        "relvol_umbral_swing_max", relvol_umbral_swing_min + 0.1, 6.0
    )
    atr_pct_umbral_swing_min = trial.suggest_float("atr_pct_umbral_swing_min", 1.0, 3.0)
    atr_pct_umbral_swing_max = trial.suggest_float(
        "atr_pct_umbral_swing_max", atr_pct_umbral_swing_min + 0.1, 6.0
    )
    ivr_umbral_compra = trial.suggest_float("ivr_umbral_compra", 10.0, 45.0)
    ivr_umbral_venta = trial.suggest_float("ivr_umbral_venta", ivr_umbral_compra + 1.0, 80.0)

    overrides = {
        "relvol_umbral_day": trial.suggest_float("relvol_umbral_day", 2.0, 6.0),
        "relvol_umbral_swing_min": relvol_umbral_swing_min,
        "relvol_umbral_swing_max": relvol_umbral_swing_max,
        "atr_pct_umbral_day": trial.suggest_float("atr_pct_umbral_day", 2.0, 6.0),
        "atr_pct_umbral_swing_min": atr_pct_umbral_swing_min,
        "atr_pct_umbral_swing_max": atr_pct_umbral_swing_max,
        "ivr_umbral_compra": ivr_umbral_compra,
        "ivr_umbral_venta": ivr_umbral_venta,
        "umbral_decision": trial.suggest_float("umbral_decision", 2.0, 6.0),
        "rr_target": trial.suggest_float("rr_target", 1.2, 4.0),
        # Acotado a 1.0-2.0 (antes 0.8-3.0) — hallazgo 2026-08-04: sin límite
        # realista, Optuna encontró 2.74 como "mejor" stop, que combinado con
        # rr_target alto ponía el target a ~10x ATR de distancia — en la
        # práctica inalcanzable en la ventana de simulación, así que el
        # target quedaba desactivado de facto (ver
        # docs/resumen_optimizador_2026-08.md). El rango nuevo centra el
        # default (1.5) y respeta la regla R2 ya documentada en
        # spec_modulo_3bp_4bp.md: "el stop final es el mayor entre ATR14×1.5
        # y el nivel técnico más cercano" — 1.5x es la referencia, no un
        # extremo del rango.
        "stop_atr_multiplicador": trial.suggest_float("stop_atr_multiplicador", 1.0, 2.0),
        "slippage_bps": trial.suggest_float("slippage_bps", 0.0, 15.0),
    }
    # model_copy(update=...) no re-valida — se arma con model_dump()+ScanConfig(**)
    # para que los validators de ScanConfig (rangos cruzados) corran siempre,
    # incluso si en el futuro se agrega algún campo a `overrides` sin garantizar
    # el orden por construcción.
    datos = {**config_base.model_dump(mode="json"), **overrides}
    return ScanConfig(**datos)
