import pytest
from pydantic import ValidationError

from src.trading_scanner.models import ScanConfig


def test_scanconfig_valores_default_son_validos():
    ScanConfig()


@pytest.mark.parametrize(
    "campo",
    [
        "peso_timeframe_setup",
        "peso_catalizador",
        "peso_relvol",
        "peso_atr_pct",
        "peso_sma200",
        "peso_ivr",
    ],
)
def test_pesos_negativos_son_rechazados(campo):
    with pytest.raises(ValidationError):
        ScanConfig(**{campo: -1.0})


@pytest.mark.parametrize(
    "campo",
    ["rr_target", "stop_atr_multiplicador", "target_atr_multiplicador", "relvol_umbral_day", "atr_pct_umbral_day"],
)
def test_umbrales_no_positivos_son_rechazados(campo):
    with pytest.raises(ValidationError):
        ScanConfig(**{campo: 0.0})


def test_precio_min_mayor_igual_a_precio_max_es_rechazado():
    with pytest.raises(ValidationError):
        ScanConfig(precio_min=500.0, precio_max=5.0)


def test_relvol_umbral_swing_min_mayor_igual_a_max_es_rechazado():
    with pytest.raises(ValidationError):
        ScanConfig(relvol_umbral_swing_min=3.0, relvol_umbral_swing_max=1.5)


def test_atr_pct_umbral_swing_min_mayor_igual_a_max_es_rechazado():
    with pytest.raises(ValidationError):
        ScanConfig(atr_pct_umbral_swing_min=3.0, atr_pct_umbral_swing_max=1.5)


def test_ivr_umbral_compra_mayor_igual_a_venta_es_rechazado():
    with pytest.raises(ValidationError):
        ScanConfig(ivr_umbral_compra=50.0, ivr_umbral_venta=30.0)


def test_min_criterios_calculables_fuera_de_rango_es_rechazado():
    with pytest.raises(ValidationError):
        ScanConfig(min_criterios_calculables=0)
    with pytest.raises(ValidationError):
        ScanConfig(min_criterios_calculables=7)


def test_posiciones_simultaneas_max_no_positivo_es_rechazado():
    with pytest.raises(ValidationError):
        ScanConfig(posiciones_simultaneas_max=0)


def test_slippage_bps_negativo_es_rechazado():
    with pytest.raises(ValidationError):
        ScanConfig(slippage_bps=-1.0)


def test_peso_cero_desactiva_criterio_sin_error():
    ScanConfig(peso_relvol=0.0)
