from datetime import datetime, timedelta

import polars as pl
import pytest

from src.trading_scanner.backtest.simulator import _truncar_a_cierre_forzado, simular
from src.trading_scanner.models import ModoSalida, ScanConfig

# Timestamps crudos son UTC (epoch ms casteado directo, ver
# schwab_history._parse_response) — 2026-01-15 es un día de invierno
# (EST, UTC-5), así que NY 09:30 = UTC 14:30, NY 15:55 = UTC 20:55,
# NY 16:00 = UTC 21:00.
_NY_0930_UTC = datetime(2026, 1, 15, 14, 30)


def _velas(n: int, precio_base: float = 100.0, paso_minutos: int = 5, alza: float = 0.0) -> pl.DataFrame:
    """n velas de 5m consecutivas arrancando en la apertura NY, sin tocar
    nunca stop ni target (rango chico) salvo que `alza` empuje el precio."""
    timestamps = [_NY_0930_UTC + timedelta(minutes=paso_minutos * i) for i in range(n)]
    precios = [precio_base + alza * i for i in range(n)]
    return pl.DataFrame({
        "timestamp": timestamps,
        "open": precios,
        "high": [p + 0.05 for p in precios],
        "low": [p - 0.05 for p in precios],
        "close": precios,
        "volume": [100_000] * n,
    })


# ── _truncar_a_cierre_forzado: la función pura ──────────────────────────────


def test_truncar_mantiene_velas_hasta_las_15_55_ny_inclusive():
    # NY 09:30 + 78 velas de 5m = hasta NY 15:55 (78*5=390min=6h30m).
    velas = _velas(n=79)  # una vela más, hasta NY 16:00
    resultado = _truncar_a_cierre_forzado(velas)
    assert resultado.height == 78


def test_truncar_no_hace_nada_si_ya_termina_antes_del_cierre():
    velas = _velas(n=10)  # termina bien antes de las 15:55 NY
    resultado = _truncar_a_cierre_forzado(velas)
    assert resultado.height == 10


def test_truncar_df_vacio_no_rompe():
    vacio = pl.DataFrame({"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []})
    assert _truncar_a_cierre_forzado(vacio).is_empty()


# ── simular(): el cierre forzado aplica a los 3 modos por igual ────────────


@pytest.mark.parametrize("modo", [ModoSalida.FIXED_RR, ModoSalida.TRAILING_EOD, ModoSalida.PARTIAL_SCALE])
def test_simular_no_sostiene_mas_alla_de_las_15_55_ny(modo):
    """Antes del fix, los 3 modos caían al último valor de `velas_dia` sin
    importar la hora — acá `velas_dia` llega con datos hasta bien entrada
    la noche (como pasa en producción, ver comentario en simulator.py), con
    una tendencia alcista constante y sin tocar nunca stop/target (rango
    amplio a propósito). Sin el fix, la salida EOD usaría el precio de la
    vela 199 (la última); con el fix, tiene que usar el de la vela 77 (la
    última con hora NY <= 15:55) — ambos valores son bien distintos porque
    el precio sube $1 por vela, así que el test falla de forma inequívoca
    si el truncado no se aplica."""
    config = ScanConfig(modo_salida=modo, stop_atr_multiplicador=50.0, rr_target=50.0)
    velas = _velas(n=200, precio_base=100.0, alza=1.0)

    resultado = simular(velas, atr=1.0, config=config)

    assert resultado is not None
    assert resultado.motivo_salida in ("eod", "parcial+trailing")
    precio_vela_77 = 100.0 + 77  # última vela con hora NY <= 15:55 (índice 0-based)
    precio_vela_199 = 100.0 + 199  # última vela de la serie completa, sin truncar
    assert resultado.precio_salida == pytest.approx(precio_vela_77, abs=0.5)
    assert resultado.precio_salida < precio_vela_199 - 50
