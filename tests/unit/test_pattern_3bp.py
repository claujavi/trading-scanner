from datetime import date, datetime, timedelta

import pytest

from src.trading_scanner.engine.pattern_3bp import Detector3BP, Estado3BP, VelaPattern
from src.trading_scanner.models import ResultadoBp34

_T0 = datetime(2026, 7, 31, 9, 30)


def _v(i: int, high: float, low: float, close: float, volume: float = 100_000) -> VelaPattern:
    return VelaPattern(timestamp=_T0 + timedelta(minutes=5 * i), high=high, low=low, close=close, volume=volume)


def _detector(**overrides) -> Detector3BP:
    base = dict(
        wrb_multiplicador=2.0,
        tolerancia_pct=0.25,
        n_invalidacion=10,
        ventana_inicio_barras=3,
        volumen_confirmado_mult=2.0,
    )
    base.update(overrides)
    return Detector3BP(**base)


# ── Barra 1 (WRB) ────────────────────────────────────────────────────────


def test_barra1_detectada_cuando_rango_supera_umbral():
    """Ejemplo de la spec: barra 1 min=2, max=10 (rango=8). ATR=4, k=2 ->
    umbral=8, rango exacto en el umbral -> confirma (>=)."""
    det = _detector()
    evento = det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)

    assert evento is not None
    assert evento.estado == Estado3BP.POSIBLE
    assert det.estado == Estado3BP.POSIBLE


def test_barra1_no_detectada_si_rango_no_alcanza_el_umbral():
    det = _detector()
    evento = det.procesar_barra(_v(0, high=9.9, low=2.0, close=9.0), atr14=4.0)  # rango=7.9 < 8

    assert evento is None
    assert det.estado == Estado3BP.SIN_PATRON


def test_barra1_no_se_marca_en_medio_de_tendencia_ya_extendida():
    """Si una barra igual de amplia ya apareció dentro de la ventana de
    inicio, la siguiente barra amplia NO cuenta como barra 1 nueva."""
    det = _detector(ventana_inicio_barras=3)
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)  # ya WRB -> pasa a POSIBLE
    # Forzar vuelta a SIN_PATRON con una barra que invalida, dejando el
    # rango amplio anterior todavía dentro de la ventana de 3 barras.
    evento_invalida = det.procesar_barra(_v(1, high=3.0, low=1.0, close=1.5), atr14=4.0)
    assert evento_invalida.estado == Estado3BP.SIN_PATRON

    # Nueva barra amplia — pero la barra 0 (rango 8) sigue en la ventana.
    evento = det.procesar_barra(_v(2, high=12.0, low=4.0, close=11.0), atr14=4.0)  # rango=8
    assert evento is None
    assert det.estado == Estado3BP.SIN_PATRON


# ── Barra 2 / grupo — condición de posición y techo ─────────────────────


def test_barra2_confirma_grupo_con_minimo_en_el_punto_medio():
    """Ejemplo exacto de la spec: pm = 2 + 0.5*8 = 6 -> low de barra 2 >= 6."""
    det = _detector()
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)

    evento = det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)

    assert evento is not None
    assert evento.estado == Estado3BP.ESPERANDO_ENTRADA
    assert det.estado == Estado3BP.ESPERANDO_ENTRADA


def test_barra2_no_confirma_si_minimo_queda_por_debajo_del_punto_medio():
    det = _detector()
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)

    evento = det.procesar_barra(_v(1, high=9.0, low=5.9, close=8.0), atr14=4.0)  # low < pm=6

    assert evento is None
    assert det.estado == Estado3BP.SIN_PATRON  # sin estructura mínima, se descarta


def test_barra2_no_confirma_si_supera_el_techo_con_tolerancia():
    # techo = M1(10) + tolerancia(0.25*8=2) = 12
    det = _detector(tolerancia_pct=0.25)
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)

    evento = det.procesar_barra(_v(1, high=12.1, low=7.0, close=11.0), atr14=4.0)  # high > 12

    assert evento is None
    assert det.estado == Estado3BP.SIN_PATRON


# ── Resolución dinámica 3BP vs 4BP ──────────────────────────────────────


def test_dispara_3bp_con_una_sola_barra_de_grupo():
    det = _detector()
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)  # barra 1
    det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)  # barra 2 (grupo)

    evento = det.procesar_barra(_v(2, high=10.5, low=9.0, close=10.3), atr14=4.0)  # gatillo

    assert evento.estado == Estado3BP.ENTRADA
    assert evento.tipo == "3BP"
    assert evento.entry == 10.0  # max(barra1.high=10, grupo highs=[9])
    assert evento.stop == 2.0    # min(barra1.low=2, grupo lows=[6])
    assert evento.barra1_wrb_ratio == 2.0  # rango barra1 (8) / atr14 (4) al detectarla
    assert det.estado == Estado3BP.SIN_PATRON  # se resetea después de disparar


def test_barra1_wrb_ratio_escala_con_el_rango_de_la_barra1():
    """El ratio se calcula contra el ATR14 vigente CUANDO se detectó la
    barra 1, no contra el ATR14 de la barra gatillo (pueden pasar varias
    barras, y ATR14 varía de una llamada a la otra en el uso real)."""
    det = _detector()
    det.procesar_barra(_v(0, high=13.0, low=1.0, close=12.0), atr14=4.0)  # barra1, rango=12
    det.procesar_barra(_v(1, high=12.0, low=7.0, close=11.0), atr14=9.0)  # grupo, atr14 distinto

    evento = det.procesar_barra(_v(2, high=13.5, low=12.0, close=13.3), atr14=1.0)  # gatillo

    assert evento.estado == Estado3BP.ENTRADA
    assert evento.barra1_wrb_ratio == 3.0  # 12 / 4.0 (atr14 de la barra1), no /9.0 ni /1.0


def test_descarta_el_patron_si_una_tercera_barra_candidata_a_grupo_excede_el_tope():
    """"3 y 4 Bar Play" es una definición cerrada — el grupo tiene tope
    duro de 2 barras (bar2+bar3). Una barra que calificaría como una 3ra
    barra de grupo no lo extiende: descarta el patrón entero."""
    det = _detector()
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)   # barra 1
    det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)   # barra 2 (grupo, tamaño 1)
    det.procesar_barra(_v(2, high=9.5, low=6.5, close=8.5), atr14=4.0)   # barra 3 (grupo, tamaño 2 = tope)
    assert det.estado == Estado3BP.ESPERANDO_ENTRADA

    # Candidata a 4ta barra: confirma la condición de grupo (low=7.0 >= pm=6,
    # high=9.4 <= techo=12) pero no dispara (9.4 <= nivel_gatillo=max(10,9,9.5)=10)
    # ni invalida (close=9.0 >= 2).
    evento = det.procesar_barra(_v(3, high=9.4, low=7.0, close=9.0), atr14=4.0)

    assert evento is not None
    assert evento.estado == Estado3BP.SIN_PATRON
    assert det.estado == Estado3BP.SIN_PATRON


def test_dispara_4bp_con_dos_barras_de_grupo():
    det = _detector()
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)   # barra 1
    det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)   # barra 2 (grupo)
    evento_barra3 = det.procesar_barra(_v(2, high=9.5, low=6.5, close=8.5), atr14=4.0)  # barra 3 (grupo, no rompe)
    assert evento_barra3 is None  # sigue en ESPERANDO_ENTRADA, sin evento por cada barra
    assert det.estado == Estado3BP.ESPERANDO_ENTRADA

    evento = det.procesar_barra(_v(3, high=10.5, low=9.0, close=10.3), atr14=4.0)  # gatillo

    assert evento.estado == Estado3BP.ENTRADA
    assert evento.tipo == "4BP"


# ── Invalidación ─────────────────────────────────────────────────────────


def test_invalida_si_una_barra_cierra_bajo_el_minimo_de_barra1_desde_posible():
    det = _detector()
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)

    evento = det.procesar_barra(_v(1, high=3.0, low=1.0, close=1.5), atr14=4.0)  # close < 2

    assert evento.estado == Estado3BP.SIN_PATRON
    assert det.estado == Estado3BP.SIN_PATRON


def test_invalida_si_una_barra_cierra_bajo_el_minimo_de_barra1_desde_esperando_entrada():
    det = _detector()
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)
    det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)  # ESPERANDO_ENTRADA

    evento = det.procesar_barra(_v(2, high=5.0, low=1.0, close=1.9), atr14=4.0)  # close < 2

    assert evento.estado == Estado3BP.SIN_PATRON
    assert det.estado == Estado3BP.SIN_PATRON


def test_invalida_por_n_barras_sin_ruptura_desde_estado2():
    det = _detector(n_invalidacion=2)
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)
    det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)  # ESPERANDO_ENTRADA, contador en 0

    # Dos barras "neutras": no confirman grupo (low < pm=6), no invalidan
    # (close >= 2), no disparan (high < nivel_gatillo=10).
    evento1 = det.procesar_barra(_v(2, high=8.0, low=5.0, close=6.0), atr14=4.0)
    assert evento1 is None
    assert det.estado == Estado3BP.ESPERANDO_ENTRADA

    evento2 = det.procesar_barra(_v(3, high=8.0, low=5.0, close=6.0), atr14=4.0)
    assert evento2 is not None
    assert evento2.estado == Estado3BP.SIN_PATRON
    assert det.estado == Estado3BP.SIN_PATRON


# ── Confirmación de volumen (tier) ──────────────────────────────────────


def test_tier_confirmado_con_volumen_alto_en_barra_gatillo():
    det = _detector(volumen_confirmado_mult=2.0)
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)
    det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)

    evento = det.procesar_barra(
        _v(2, high=10.5, low=9.0, close=10.3, volume=250_000), atr14=4.0, volumen_promedio=100_000
    )

    assert evento.tier == "confirmado"


def test_tier_sin_confirmar_con_volumen_bajo_en_barra_gatillo():
    det = _detector(volumen_confirmado_mult=2.0)
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)
    det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)

    evento = det.procesar_barra(
        _v(2, high=10.5, low=9.0, close=10.3, volume=150_000), atr14=4.0, volumen_promedio=100_000
    )

    assert evento.tier == "sin_confirmar"


def test_tier_sin_confirmar_si_no_se_provee_volumen_promedio():
    """La confirmación de volumen es opcional y no bloqueante (spec) — sin
    dato de referencia, la señal igual dispara, solo que sin tier."""
    det = _detector()
    det.procesar_barra(_v(0, high=10.0, low=2.0, close=9.0), atr14=4.0)
    det.procesar_barra(_v(1, high=9.0, low=6.0, close=8.0), atr14=4.0)

    evento = det.procesar_barra(_v(2, high=10.5, low=9.0, close=10.3), atr14=4.0)

    assert evento.estado == Estado3BP.ENTRADA
    assert evento.tier == "sin_confirmar"


# ── SeguidorPosicion3BP — seguimiento en vivo, vela a vela ────────────────
# Misma semántica que backtest/walker_3bp.py::_resolver_entrada, pero
# alimentada una vela por vez en vez de recibir de una sola vez todas las
# velas futuras del día. `_T_NY` son timestamps UTC reales (no los índices
# relativos de _v() de arriba) porque acá sí importa la hora NY real.

from src.trading_scanner.engine.pattern_3bp import SeguidorPosicion3BP, fecha_ny, minutos_desde_apertura_ny  # noqa: E402

_APERTURA_UTC = datetime(2026, 1, 2, 14, 30)  # 9:30 NY (EST, UTC-5) del 2026-01-02
_FECHA = fecha_ny(_APERTURA_UTC)


def _vp(minutos_desde_apertura: int, high: float, low: float, close: float) -> VelaPattern:
    ts = _APERTURA_UTC + timedelta(minutes=minutos_desde_apertura)
    return VelaPattern(timestamp=ts, high=high, low=low, close=close, volume=1000.0)


def _seguidor(**overrides) -> SeguidorPosicion3BP:
    base = dict(ticker="AAPL", timeframe="5m", fecha=_FECHA, entry=10.0, stop=9.0, target=12.0, slippage_bps=0.0)
    base.update(overrides)
    return SeguidorPosicion3BP(**base)


def test_minutos_desde_apertura_ny_en_la_apertura():
    assert minutos_desde_apertura_ny(_APERTURA_UTC) == 0


def test_fecha_ny_devuelve_la_fecha_de_trading():
    assert fecha_ny(_APERTURA_UTC) == date(2026, 1, 2)


def test_seguidor_toca_target():
    seg = _seguidor()
    r = seg.procesar_vela(_vp(5, high=12.5, low=11.0, close=12.2))

    assert r is not None
    resultado, resultado_r, mfe_r, mae_r, tiempo = r
    assert resultado == ResultadoBp34.TARGET
    assert resultado_r == 2.0  # target_r = (12-10)/(10-9)
    assert mfe_r == pytest.approx(2.5)
    assert tiempo == 0  # se resolvió en la primera vela vista
    assert seg.resuelto is True


def test_seguidor_toca_stop():
    seg = _seguidor()
    r = seg.procesar_vela(_vp(5, high=10.2, low=8.5, close=9.0))

    assert r[0] == ResultadoBp34.STOP
    assert r[1] == -1.0


def test_seguidor_ambos_en_la_misma_vela_gana_el_stop():
    seg = _seguidor()
    r = seg.procesar_vela(_vp(5, high=15.0, low=8.5, close=9.0))
    assert r[0] == ResultadoBp34.STOP


def test_seguidor_acumula_mfe_mae_a_traves_de_varias_velas():
    seg = _seguidor(target=20.0)  # target lejos, no se toca en este test
    assert seg.procesar_vela(_vp(0, high=10.5, low=9.5, close=10.2)) is None
    assert seg.procesar_vela(_vp(5, high=11.5, low=9.8, close=11.0)) is None
    r = seg.procesar_vela(_vp(10, high=10.8, low=8.2, close=9.0))  # ahora sí toca el stop (low<=9.0)

    assert r[0] == ResultadoBp34.STOP
    assert r[2] == pytest.approx(1.5)   # mfe: max((11.5-10)/1, ...) = 1.5
    assert r[3] == pytest.approx(-1.8)  # mae: min((8.2-10)/1, ...) = -1.8
    assert r[4] == 10  # tercera vela vista (índice 2) * 5 min


def test_seguidor_cierre_forzado_a_las_15_55_ny_usa_el_cierre_de_la_ultima_vela():
    seg = _seguidor(target=100.0)  # jamás se toca
    minutos_a_las_1550 = 385 - 5  # 15:50 NY, última vela normal antes del cierre
    assert seg.procesar_vela(_vp(minutos_a_las_1550, high=10.2, low=9.8, close=10.1)) is None
    # la siguiente (15:55) es la última permitida — no toca nada, cierra forzado con SU close
    r = seg.procesar_vela(_vp(385, high=10.3, low=9.9, close=10.15))

    assert r[0] == ResultadoBp34.SIN_DEFINIR
    assert r[1] == pytest.approx(0.15)  # (10.15-10)/1
    assert seg.resuelto is True


def test_seguidor_vela_de_otro_dia_fuerza_cierre_con_la_ultima_vela_valida():
    seg = _seguidor(target=100.0)
    seg.procesar_vela(_vp(5, high=10.3, low=9.9, close=10.1))
    manana = VelaPattern(timestamp=_APERTURA_UTC + timedelta(days=1, minutes=5), high=11.0, low=10.0, close=10.5, volume=1000.0)

    r = seg.procesar_vela(manana)
    assert r[0] == ResultadoBp34.SIN_DEFINIR
    assert r[1] == pytest.approx(0.1)  # cierre de la vela de HOY (10.1), no de la de mañana


def test_seguidor_sin_ninguna_vela_valida_cierra_en_cero():
    """Caso raro: la reconciliación tras un reinicio no encuentra ninguna
    vela del día (ej. Schwab sin historial ese día) — no hay dato real."""
    seg = _seguidor()
    otro_dia = VelaPattern(timestamp=_APERTURA_UTC + timedelta(days=1), high=10.0, low=10.0, close=10.0, volume=1000.0)

    r = seg.procesar_vela(otro_dia)
    assert r == (ResultadoBp34.SIN_DEFINIR, 0.0, 0.0, 0.0, 0)


def test_seguidor_ya_resuelto_no_hace_nada_en_llamadas_posteriores():
    seg = _seguidor()
    seg.procesar_vela(_vp(5, high=12.5, low=11.0, close=12.2))  # resuelve por target
    assert seg.procesar_vela(_vp(10, high=999.0, low=0.01, close=500.0)) is None


def test_seguidor_aplica_slippage_igual_que_resolver_entrada():
    # mismo ejemplo que test_slippage_en_stop_pierde_mas_de_1r de test_walker_3bp.py
    seg = _seguidor(slippage_bps=10.0)
    r = seg.procesar_vela(_vp(5, high=10.2, low=8.5, close=9.0))
    assert r[0] == ResultadoBp34.STOP
    assert r[1] == pytest.approx(-1.019)
