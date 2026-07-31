from datetime import date, datetime

from src.trading_scanner.engine.evaluator import DatosTickerCompletos, _umbral_variacion_diaria, evaluar
from src.trading_scanner.models import Clasificacion, FuenteDatos, ScanConfig


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


# ── _umbral_variacion_diaria: fórmula pura ──────────────────────────────────


def test_umbral_al_precio_de_referencia_es_igual_al_base():
    config = ScanConfig()  # variacion_diaria_min_pct=2.0, referencia=20.0
    assert _umbral_variacion_diaria(20.0, config) == 2.0


def test_umbral_sube_para_accion_barata_clampeado_al_maximo():
    config = ScanConfig()  # escala_max=2.5
    # factor bruto = 20/6 = 3.33... -> clampeado a 2.5
    assert _umbral_variacion_diaria(6.0, config) == 2.0 * 2.5


def test_umbral_baja_para_accion_cara_clampeado_al_minimo():
    config = ScanConfig()  # escala_min=0.5
    # factor bruto = 20/200 = 0.1 -> clampeado a 0.5
    assert _umbral_variacion_diaria(200.0, config) == 2.0 * 0.5


def test_umbral_intermedio_sin_clamp():
    config = ScanConfig()
    # precio=40 -> factor = 20/40 = 0.5 (coincide con escala_min, sin clamp real)
    assert _umbral_variacion_diaria(40.0, config) == 2.0 * 0.5


def test_umbral_precio_cero_no_rompe_usa_base_sin_escalar():
    config = ScanConfig()
    assert _umbral_variacion_diaria(0.0, config) == config.variacion_diaria_min_pct


# ── Integración con evaluar(): el filtro de entrada usa el umbral escalado ──


def test_accion_barata_con_variacion_antes_suficiente_ahora_se_descarta():
    """precio=$6, variacion=3.5% -> antes pasaba (>= 2.0%), ahora el umbral
    escalado es 5.0% y 3.5% ya no alcanza."""
    config = ScanConfig()
    datos = make_base_data(precio=6.0, variacion_diaria_pct=3.5)

    resultado = evaluar(datos, config)

    assert resultado.clasificacion == Clasificacion.DESCARTAR
    assert "FILTRO_ENTRADA:variacion_diaria" in resultado.criterios_incompletos


def test_accion_cara_con_variacion_antes_insuficiente_ahora_pasa():
    """precio=$200, variacion=1.2% -> antes no pasaba (< 2.0%), ahora el
    umbral escalado es 1.0% y 1.2% sí alcanza."""
    config = ScanConfig()
    datos = make_base_data(precio=200.0, variacion_diaria_pct=1.2)

    resultado = evaluar(datos, config)

    assert "FILTRO_ENTRADA:variacion_diaria" not in resultado.criterios_incompletos


def test_accion_al_precio_de_referencia_mantiene_comportamiento_anterior():
    config = ScanConfig()
    datos = make_base_data(precio=20.0, variacion_diaria_pct=1.9)

    resultado = evaluar(datos, config)

    assert resultado.clasificacion == Clasificacion.DESCARTAR
    assert "FILTRO_ENTRADA:variacion_diaria" in resultado.criterios_incompletos
