import pytest

from datetime import date, datetime

from src.trading_scanner.models import ScanConfig, Clasificacion, FuenteDatos
from src.trading_scanner.engine.evaluator import DatosTickerCompletos, evaluar


def make_base_data(**overrides) -> DatosTickerCompletos:
    base = {
        "ticker": "AAPL",
        "fecha": date(2026, 6, 17),
        "timestamp": datetime(2026, 6, 17, 13, 0),
        "fuente": FuenteDatos.LIVE,
        "precio": 170.0,
        "variacion_diaria_pct": 3.5,
        "relvol": 3.5,
        "atr_pct": 4.0,
        "volumen_actual": 1_200_000,
        "sobre_sma200": True,
        "sobre_ema50": True,
        "cruce_ema_921_5m": True,
        "cruce_ema_921_15m": True,
        "cruce_ema_921_4h": True,
        "cruce_ema_921_d": True,
        "ivr": 25.0,
        "warning_calendar": "GREEN",
        "earnings_24h": False,
        "evento_macro_24h": False,
        "filing_8k_24h": False,
        "upgrade_downgrade_24h": False,
        "catalizador_detectado": False,
    }
    base.update(overrides)
    return DatosTickerCompletos(**base)


def test_evaluador_classifica_day_con_setup_bullish_y_relvol_alto():
    config = ScanConfig()
    datos = make_base_data()

    resultado = evaluar(datos, config)

    assert resultado.clasificacion == Clasificacion.DAY
    assert resultado.score_day > resultado.score_swing
    assert resultado.confianza == 1.0
    assert resultado.score_max_posible == 7.0
    assert resultado.criterios_incompletos == []


def test_evaluador_classifica_swing_con_setup_bearish_y_relvol_moderado():
    config = ScanConfig()
    datos = make_base_data(
        cruce_ema_921_5m=False,
        cruce_ema_921_15m=False,
        cruce_ema_921_4h=False,
        cruce_ema_921_d=False,
        relvol=2.0,
        atr_pct=2.0,
        sobre_sma200=False,
        ivr=60.0,
    )

    resultado = evaluar(datos, config)

    assert resultado.clasificacion == Clasificacion.SWING
    assert resultado.score_swing > resultado.score_day
    assert resultado.score_max_posible == 7.0
    assert resultado.confianza == pytest.approx(resultado.score_swing / resultado.score_max_posible)


def test_evaluador_retiene_ambiguo_si_ambos_scores_superan_el_umbral():
    config = ScanConfig(umbral_decision=1.0)
    datos = make_base_data(
        cruce_ema_921_5m=True,
        cruce_ema_921_15m=True,
        cruce_ema_921_4h=True,
        cruce_ema_921_d=True,
        catalizador_detectado=True,
        warning_calendar="GREEN",
        relvol=1.0,
        atr_pct=1.0,
        sobre_sma200=False,
        ivr=55.0,
    )

    resultado = evaluar(datos, config)

    assert resultado.clasificacion == Clasificacion.AMBIGUO
    assert resultado.score_day == pytest.approx(resultado.score_swing)
    assert resultado.score_max_posible == 7.0


def test_evaluador_descarta_por_insuficiente_data():
    config = ScanConfig(min_criterios_calculables=5)
    datos = make_base_data(
        relvol=None,
        atr_pct=None,
        sobre_sma200=None,
        ivr=None,
        catalizador_detectado=False,
        warning_calendar=None,
    )

    resultado = evaluar(datos, config)

    assert resultado.clasificacion == Clasificacion.DESCARTAR
    assert "INSUFICIENTE_DATA" in resultado.criterios_incompletos
    assert resultado.score_day == 0.0
    assert resultado.score_swing == 0.0
    assert resultado.score_max_posible == 0.0


def test_evaluador_marca_criterios_incompletos_correctamente():
    config = ScanConfig(min_criterios_calculables=3)
    datos = make_base_data(relvol=None, atr_pct=None)

    resultado = evaluar(datos, config)

    assert "relvol" in resultado.criterios_incompletos
    assert "atr_pct" in resultado.criterios_incompletos
    assert resultado.score_max_posible == 5.0
    assert resultado.clasificacion != Clasificacion.DESCARTAR


def test_pesos_afectan_score():
    config_base = ScanConfig()
    datos = make_base_data()

    resultado_base = evaluar(datos, config_base)

    config_peso_alto = ScanConfig(peso_relvol=3.0)
    resultado_peso_alto = evaluar(datos, config_peso_alto)

    assert resultado_base.score_day != resultado_peso_alto.score_day
    assert resultado_peso_alto.score_max_posible == pytest.approx(9.0)  # 6 pesos en 1.0 + peso_relvol en 3.0


def test_slippage_no_afecta_score():
    config_base = ScanConfig(slippage_bps=5.0)
    datos = make_base_data()

    resultado_base = evaluar(datos, config_base)

    config_alto_slippage = ScanConfig(slippage_bps=50.0)
    resultado_alto_slippage = evaluar(datos, config_alto_slippage)

    assert resultado_base.score_day == pytest.approx(resultado_alto_slippage.score_day)
    assert resultado_base.score_swing == pytest.approx(resultado_alto_slippage.score_swing)
