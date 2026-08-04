from datetime import date, datetime, timedelta

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


def _velas_multidia(n_dias: int, velas_por_dia: int = 79, precio_base: float = 100.0, alza_diaria: float = 0.0) -> pl.DataFrame:
    """`n_dias` sesiones hábiles consecutivas (arrancando el jueves
    2026-01-15, EST — mismo día base que _NY_0930_UTC, evita cruzar DST),
    `velas_por_dia` velas de 5m cada una desde la apertura NY. El precio
    sube `alza_diaria` al arrancar cada día nuevo, para poder verificar en
    qué día exacto se resuelve un trade multi-día."""
    timestamps: list[datetime] = []
    precios: list[float] = []
    fecha = date(2026, 1, 15)
    precio = precio_base
    for _ in range(n_dias):
        apertura = datetime.combine(fecha, datetime.min.time()) + timedelta(hours=14, minutes=30)
        for i in range(velas_por_dia):
            timestamps.append(apertura + timedelta(minutes=5 * i))
            precios.append(precio)
        precio += alza_diaria
        fecha += timedelta(days=1)
        while fecha.weekday() >= 5:
            fecha += timedelta(days=1)
    return pl.DataFrame({
        "timestamp": timestamps,
        "open": precios,
        "high": [p + 0.05 for p in precios],
        "low": [p - 0.05 for p in precios],
        "close": precios,
        "volume": [100_000] * len(precios),
    })


def test_truncar_con_fecha_limite_no_corta_los_dias_intermedios():
    """fecha_limite debe cortar el ÚLTIMO día permitido, dejando pasar
    completos los días anteriores — a diferencia del comportamiento default
    (sin fecha_limite), que corta el PRIMER día."""
    velas = _velas_multidia(n_dias=3, velas_por_dia=79)  # 237 velas totales
    fecha_dia_3 = date(2026, 1, 19)  # 15(jue) -> 16(vie) -> 19(lun), saltando fin de semana

    resultado = _truncar_a_cierre_forzado(velas, fecha_limite=fecha_dia_3)

    # días 1 y 2 completos (79 c/u) + día 3 cortado a las 15:55 (78 velas)
    assert resultado.height == 79 + 79 + 78


def test_truncar_sin_fecha_limite_sigue_cortando_el_primer_dia():
    velas = _velas_multidia(n_dias=3, velas_por_dia=79)
    resultado = _truncar_a_cierre_forzado(velas)
    assert resultado.height == 78  # solo el día 1, truncado


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


# ── simular(): sostenimiento multi-día (SWING, fecha_limite_cierre) ────────


def test_simular_con_fecha_limite_cierre_sostiene_varios_dias_hasta_target():
    """Target que no se alcanza el día 1 pero sí el día 2 — sin
    fecha_limite_cierre esto se truncaría al día 1 y resolvería por eod,
    nunca por target. Con fecha_limite_cierre (día 3), el trade sigue vivo
    el día 2 y toca el target ahí."""
    config = ScanConfig(modo_salida=ModoSalida.FIXED_RR, stop_atr_multiplicador=1.0, rr_target=2.0)
    # entrada=100, atr=1 -> stop_dist=1, target=102. Sube $0.5/día: recién
    # el día 3 alguna vela llega a high=102 (100 + 2*0.5 + 0.05 margen high).
    velas = _velas_multidia(n_dias=3, velas_por_dia=10, precio_base=100.0, alza_diaria=1.0)
    fecha_limite = date(2026, 1, 19)  # día 3

    resultado = simular(velas, atr=1.0, config=config, fecha_limite_cierre=fecha_limite)

    assert resultado is not None
    assert resultado.motivo_salida == "target"


def test_simular_con_fecha_limite_cierre_resuelve_eod_en_el_ultimo_dia_no_en_el_primero():
    """Sin tocar stop ni target, un SWING sostenido debe resolverse por el
    cierre del ÚLTIMO día permitido (fecha_limite_cierre), no por el
    cierre del primer día — a diferencia de un DAY (sin fecha_limite_cierre)."""
    config = ScanConfig(modo_salida=ModoSalida.FIXED_RR, stop_atr_multiplicador=50.0, rr_target=50.0)
    velas = _velas_multidia(n_dias=3, velas_por_dia=10, precio_base=100.0, alza_diaria=1.0)
    fecha_limite = date(2026, 1, 19)  # día 3

    resultado = simular(velas, atr=1.0, config=config, fecha_limite_cierre=fecha_limite)

    assert resultado is not None
    assert resultado.motivo_salida == "eod"
    # precio del día 3 (100 + 2*1.0 = 102), no del día 1 (100)
    assert resultado.precio_salida == pytest.approx(102.0, abs=0.5)
