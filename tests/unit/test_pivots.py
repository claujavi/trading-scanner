import polars as pl
import pytest

from src.trading_scanner.engine.pivots import _comparar, _detectar_pivotes, _racha, detect_estructura_pivotes
from src.trading_scanner.models import ScanConfig


# ── _detectar_pivotes: fractal L barras a cada lado ─────────────────────────


def test_detectar_pivote_alto_ejemplo_de_la_spec():
    # Mismo ejemplo numérico de docs/spec_criterio_pivotes.md: pivote alto
    # confirmado en idx=8 (valor 11.8), L=3.
    highs = [10.0, 10.5, 11.2, 10.8, 10.3, 9.9, 10.4, 11.0, 11.8, 11.3, 10.9, 10.5]
    pivotes = _detectar_pivotes(highs, ventana_l=3, es_alto=True)
    assert pivotes == [11.8]


def test_detectar_pivote_alto_falla_si_no_es_estrictamente_mayor_a_vecino_previo():
    # idx=3 (10.8) falla porque idx=2 (11.2) es mayor — no debe aparecer.
    highs = [10.0, 10.5, 11.2, 10.8, 10.3, 9.9, 10.4, 11.0, 11.8, 11.3, 10.9, 10.5]
    pivotes = _detectar_pivotes(highs, ventana_l=3, es_alto=True)
    assert 10.8 not in pivotes


def test_detectar_pivote_bajo_es_independiente_del_alto():
    lows = [10.0, 9.8, 9.0, 9.5, 9.9, 10.5, 10.0, 9.4, 8.7, 9.2, 9.6, 10.0]
    pivotes = _detectar_pivotes(lows, ventana_l=3, es_alto=False)
    assert pivotes == [8.7]


def test_detectar_pivotes_serie_corta_no_rompe():
    assert _detectar_pivotes([1.0, 2.0, 3.0], ventana_l=3, es_alto=True) == []


def test_detectar_dos_pivotes_altos_consecutivos():
    # idx=3 (12.0) y idx=10 (13.0) ambos confirmados con L=2.
    highs = [10, 10.5, 11, 12.0, 11.5, 11.0, 10.8, 11.2, 11.8, 12.4, 13.0, 12.5, 12.0]
    pivotes = _detectar_pivotes(highs, ventana_l=2, es_alto=True)
    assert pivotes == [12.0, 13.0]


# ── _comparar: tolerancia en múltiplos de ATR ───────────────────────────────


def test_comparar_diferencia_dentro_de_tolerancia_es_equal():
    # Ejemplo de la spec: ATR=2.00, tolerancia=0.5 -> margen=1.00. 50.00 -> 50.80 (+0.80) = Equal.
    assert _comparar(actual=50.80, anterior=50.00, atr=2.00, tolerancia_atr=0.5) == "Equal"


def test_comparar_diferencia_supera_margen_es_higher():
    # 50.00 -> 51.20 (+1.20) > margen 1.00 -> Higher.
    assert _comparar(actual=51.20, anterior=50.00, atr=2.00, tolerancia_atr=0.5) == "Higher"


def test_comparar_diferencia_negativa_supera_margen_es_lower():
    assert _comparar(actual=48.50, anterior=50.00, atr=2.00, tolerancia_atr=0.5) == "Lower"


def test_comparar_en_el_borde_exacto_del_margen_es_equal():
    # diferencia == margen (no supera estrictamente) -> Equal.
    assert _comparar(actual=51.00, anterior=50.00, atr=2.00, tolerancia_atr=0.5) == "Equal"


# ── _racha: mínimo de pivotes consecutivos ──────────────────────────────────


def test_racha_dos_pivotes_crecientes_es_higher():
    assert _racha([50.0, 51.20], minimos=2, atr=2.0, tolerancia_atr=0.5) == "Higher"


def test_racha_dos_pivotes_decrecientes_es_lower():
    assert _racha([50.0, 48.50], minimos=2, atr=2.0, tolerancia_atr=0.5) == "Lower"


def test_racha_pivotes_insuficientes_es_none():
    assert _racha([50.0], minimos=2, atr=2.0, tolerancia_atr=0.5) is None
    assert _racha([], minimos=2, atr=2.0, tolerancia_atr=0.5) is None


def test_racha_de_tres_requiere_las_dos_comparaciones_consistentes():
    # Con minimos=3: 50 -> 51.2 (Higher) -> 52.4 (Higher) -> racha Higher.
    assert _racha([50.0, 51.20, 52.40], minimos=3, atr=2.0, tolerancia_atr=0.5) == "Higher"
    # Con minimos=3: 50 -> 51.2 (Higher) -> 50.5 (Lower) -> mixta -> None.
    assert _racha([50.0, 51.20, 50.50], minimos=3, atr=2.0, tolerancia_atr=0.5) is None


def test_racha_equal_rompe_la_racha():
    # 50 -> 50.80 (Equal, dentro de margen) -> no es Higher ni Lower -> None.
    assert _racha([50.0, 50.80], minimos=2, atr=2.0, tolerancia_atr=0.5) is None


# ── detect_estructura_pivotes: integración con ScanConfig ──────────────────


def _df_d(highs, lows, closes):
    return pl.DataFrame({
        "high": highs,
        "low": lows,
        "close": closes,
    })


def test_estructura_none_si_df_vacio_o_none():
    config = ScanConfig()
    assert detect_estructura_pivotes(None, config) is None
    assert detect_estructura_pivotes(pl.DataFrame(), config) is None


def test_estructura_none_si_faltan_columnas():
    config = ScanConfig()
    df = pl.DataFrame({"close": [1.0, 2.0, 3.0]})
    assert detect_estructura_pivotes(df, config) is None


def test_estructura_alcista_con_pivotes_higher_higher():
    """Construye una serie donde tanto los pivotes altos como los bajos
    confirman HPH+HPL con L=3, tolerancia=0.5, mínimos=2 (defaults)."""
    config = ScanConfig()
    n = 30
    # Tendencia alcista suave con oscilación para generar pivotes claros.
    base = [100 + i * 0.5 for i in range(n)]
    highs = [base[i] + (3.0 if i % 5 == 2 else 0.5) for i in range(n)]
    lows = [base[i] - (3.0 if i % 5 == 4 else 0.5) for i in range(n)]
    closes = base
    df = _df_d(highs, lows, closes)

    resultado = detect_estructura_pivotes(df, config)

    assert resultado == "ALCISTA"


def test_estructura_bajista_con_pivotes_lower_lower():
    config = ScanConfig()
    n = 30
    base = [130 - i * 0.5 for i in range(n)]
    highs = [base[i] + (3.0 if i % 5 == 2 else 0.5) for i in range(n)]
    lows = [base[i] - (3.0 if i % 5 == 4 else 0.5) for i in range(n)]
    closes = base
    df = _df_d(highs, lows, closes)

    resultado = detect_estructura_pivotes(df, config)

    assert resultado == "BAJISTA"


def test_estructura_none_si_historial_corto():
    config = ScanConfig()
    df = _df_d([10.0] * 5, [9.0] * 5, [9.5] * 5)
    assert detect_estructura_pivotes(df, config) is None


def test_estructura_respeta_config_de_ventana_y_minimos():
    """Con pivote_ventana_l muy grande para el tamaño de la serie, no hay
    pivotes suficientes -> None, incluso si con L chico sí los habría."""
    config = ScanConfig(pivote_ventana_l=10)
    n = 20
    base = [100 + i * 0.5 for i in range(n)]
    highs = [base[i] + (3.0 if i % 5 == 2 else 0.5) for i in range(n)]
    lows = [base[i] - (3.0 if i % 5 == 4 else 0.5) for i in range(n)]
    df = _df_d(highs, lows, base)

    assert detect_estructura_pivotes(df, config) is None
