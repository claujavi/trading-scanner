from datetime import datetime, timedelta

from src.trading_scanner.engine.pattern_3bp import Detector3BP, Estado3BP, VelaPattern

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
