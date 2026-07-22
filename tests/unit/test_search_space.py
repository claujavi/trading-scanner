import optuna
import pytest

from src.trading_scanner.models import ScanConfig
from src.trading_scanner.optimizer.search_space import sugerir_config


def test_sugerir_config_con_trial_real_produce_config_valida():
    study = optuna.create_study()
    trial = study.ask()
    config = sugerir_config(trial, ScanConfig())
    assert isinstance(config, ScanConfig)
    assert config.relvol_umbral_swing_min < config.relvol_umbral_swing_max
    assert config.atr_pct_umbral_swing_min < config.atr_pct_umbral_swing_max
    assert config.ivr_umbral_compra < config.ivr_umbral_venta


@pytest.mark.parametrize("seed", range(20))
def test_sugerir_config_nunca_viola_los_validators_en_muchos_trials(seed):
    study = optuna.create_study(sampler=optuna.samplers.RandomSampler(seed=seed))
    trial = study.ask()
    config = sugerir_config(trial, ScanConfig())
    # Si algún rango cruzado quedara mal armado, ScanConfig ya habría
    # lanzado ValidationError dentro de sugerir_config.
    assert config.relvol_umbral_swing_min < config.relvol_umbral_swing_max
    assert config.atr_pct_umbral_swing_min < config.atr_pct_umbral_swing_max
    assert config.ivr_umbral_compra < config.ivr_umbral_venta


def test_sugerir_config_con_fixed_trial_reproduce_los_mismos_parametros():
    params = {
        "relvol_umbral_day": 3.5,
        "relvol_umbral_swing_min": 1.5,
        "relvol_umbral_swing_max": 3.0,
        "atr_pct_umbral_day": 3.5,
        "atr_pct_umbral_swing_min": 1.5,
        "atr_pct_umbral_swing_max": 3.0,
        "ivr_umbral_compra": 25.0,
        "ivr_umbral_venta": 55.0,
        "umbral_decision": 4.0,
        "rr_target": 2.0,
        "stop_atr_multiplicador": 1.5,
        "slippage_bps": 5.0,
    }
    trial = optuna.trial.FixedTrial(params)
    config = sugerir_config(trial, ScanConfig())
    for campo, valor in params.items():
        assert getattr(config, campo) == valor


def test_sugerir_config_no_toca_pesos_ni_los_deja_distinto_de_uno():
    study = optuna.create_study()
    trial = study.ask()
    config = sugerir_config(trial, ScanConfig())
    assert config.peso_timeframe_setup == 1.0
    assert config.peso_catalizador == 1.0
    assert config.peso_relvol == 1.0
    assert config.peso_atr_pct == 1.0
    assert config.peso_sma200 == 1.0
    assert config.peso_ivr == 1.0
