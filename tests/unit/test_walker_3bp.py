import asyncio
from datetime import date, datetime, timedelta

import polars as pl
import pytest

from src.trading_scanner.backtest import walker_3bp
from src.trading_scanner.fetchers import history_cache
from src.trading_scanner.fetchers.market_data_cache import Vela
from src.trading_scanner.models import FuenteDatos, ResultadoBp34, ScanConfig


def _v(ts: datetime, high: float, low: float, close: float, volume: float = 1000.0) -> Vela:
    return Vela(timestamp=ts, open=close, high=high, low=low, close=close, volume=volume)


# ── _df_a_velas ──────────────────────────────────────────────────────────


def test_df_a_velas_convierte_y_ordena():
    df = pl.DataFrame({
        "timestamp": [datetime(2026, 1, 2, 10, 0), datetime(2026, 1, 2, 9, 30)],
        "open": [2.0, 1.0], "high": [2.5, 1.5], "low": [1.8, 0.9],
        "close": [2.2, 1.2], "volume": [200.0, 100.0],
    })
    velas = walker_3bp._df_a_velas(df)
    assert [v.timestamp for v in velas] == [datetime(2026, 1, 2, 9, 30), datetime(2026, 1, 2, 10, 0)]
    assert velas[0].close == 1.2


def test_df_a_velas_vacio():
    df = pl.DataFrame({"timestamp": [], "open": [], "high": [], "low": [], "close": [], "volume": []})
    assert walker_3bp._df_a_velas(df) == []


# ── _resolver_entrada ────────────────────────────────────────────────────


def test_resolver_entrada_toca_target():
    velas = [
        _v(datetime(2026, 1, 2, 9, 35), high=10.5, low=9.8, close=10.2),  # barra gatillo, no toca nada
        _v(datetime(2026, 1, 2, 9, 40), high=12.5, low=11.5, close=12.2),  # toca target (12.0)
    ]
    resultado, r, mfe, mae, tiempo = walker_3bp._resolver_entrada(velas, entry=10.0, stop=9.0, target_r=2.0, timeframe="5m")

    assert resultado == ResultadoBp34.TARGET
    assert r == 2.0
    assert tiempo == 5  # segunda vela, índice 1 * 5min
    assert mfe == pytest.approx(2.5)  # (12.5-10)/1


def test_resolver_entrada_toca_stop_y_target_en_la_misma_barra_gana_stop():
    velas = [_v(datetime(2026, 1, 2, 9, 35), high=15.0, low=8.5, close=9.0)]  # toca ambos
    resultado, r, mfe, mae, tiempo = walker_3bp._resolver_entrada(velas, entry=10.0, stop=9.0, target_r=2.0, timeframe="5m")

    assert resultado == ResultadoBp34.STOP
    assert r == -1.0
    assert tiempo == 0


def test_resolver_entrada_sin_definir_al_cierre_del_dia():
    velas = [_v(datetime(2026, 1, 2, 9, 35), high=10.3, low=9.9, close=10.1)]  # no toca ninguno
    resultado, r, mfe, mae, tiempo = walker_3bp._resolver_entrada(velas, entry=10.0, stop=9.0, target_r=2.0, timeframe="5m")

    assert resultado == ResultadoBp34.SIN_DEFINIR
    assert r == pytest.approx(0.1)
    assert tiempo == 0  # única vela


def test_resolver_entrada_sin_velas_devuelve_sin_definir():
    resultado, r, mfe, mae, tiempo = walker_3bp._resolver_entrada([], entry=10.0, stop=9.0, target_r=2.0, timeframe="5m")
    assert (resultado, r, mfe, mae, tiempo) == (ResultadoBp34.SIN_DEFINIR, 0.0, 0.0, 0.0, 0)


# ── _resolver_entrada — slippage ─────────────────────────────────────────


def test_slippage_cero_es_identico_a_fills_perfectos():
    velas = [_v(datetime(2026, 1, 2, 9, 35), high=15.0, low=8.5, close=9.0)]
    sin = walker_3bp._resolver_entrada(velas, entry=10.0, stop=9.0, target_r=2.0, timeframe="5m")
    con_cero = walker_3bp._resolver_entrada(velas, entry=10.0, stop=9.0, target_r=2.0, timeframe="5m", slippage_bps=0.0)
    assert sin == con_cero
    assert sin[1] == -1.0  # exacto, no aproximado


def test_slippage_en_stop_pierde_mas_de_1r():
    # 10 bps por lado, entry 10, stop 9 (stop_dist 1.0):
    # costo = 0.001 * (9 + 10) / 1 = 0.019R
    velas = [_v(datetime(2026, 1, 2, 9, 35), high=10.2, low=8.5, close=9.0)]
    resultado, r, mfe, mae, tiempo = walker_3bp._resolver_entrada(
        velas, entry=10.0, stop=9.0, target_r=2.0, timeframe="5m", slippage_bps=10.0
    )
    assert resultado == ResultadoBp34.STOP
    assert r == pytest.approx(-1.019)


def test_slippage_en_target_gana_menos_que_target_r():
    # target = 12; costo = 0.001 * (12 + 10) / 1 = 0.022R
    velas = [_v(datetime(2026, 1, 2, 9, 35), high=12.5, low=9.8, close=12.2)]
    resultado, r, _, _, _ = walker_3bp._resolver_entrada(
        velas, entry=10.0, stop=9.0, target_r=2.0, timeframe="5m", slippage_bps=10.0
    )
    assert resultado == ResultadoBp34.TARGET
    assert r == pytest.approx(2.0 - 0.022)


def test_slippage_en_cierre_forzado():
    # cierre 10.1: (10.1 - 10)/1 = 0.1R, costo = 0.001 * (10.1 + 10) / 1 = 0.0201R
    velas = [_v(datetime(2026, 1, 2, 9, 35), high=10.3, low=9.9, close=10.1)]
    resultado, r, _, _, _ = walker_3bp._resolver_entrada(
        velas, entry=10.0, stop=9.0, target_r=2.0, timeframe="5m", slippage_bps=10.0
    )
    assert resultado == ResultadoBp34.SIN_DEFINIR
    assert r == pytest.approx(0.1 - 0.0201)


def test_slippage_pesa_mucho_mas_en_un_stop_corto_que_en_uno_ancho():
    """El motivo de todo el cambio: los mismos 10 bps se comen ~10x más R
    con un stop de 0.2% del precio que con uno de 2%."""
    def costo_en_stop(stop_dist_pct):
        entry = 10.0
        stop = entry * (1 - stop_dist_pct / 100)
        velas = [_v(datetime(2026, 1, 2, 9, 35), high=entry, low=stop * 0.99, close=stop)]
        _, r, _, _, _ = walker_3bp._resolver_entrada(
            velas, entry=entry, stop=stop, target_r=5.0, timeframe="5m", slippage_bps=10.0
        )
        return -1.0 - r

    assert costo_en_stop(0.2) == pytest.approx(0.999, abs=0.01)  # ~1R entero: el trade queda en -2R
    assert costo_en_stop(2.0) == pytest.approx(0.099, abs=0.005)
    assert costo_en_stop(0.2) > 9 * costo_en_stop(2.0)


# ── _caminar_dia — escenario 3BP completo (mismo ejemplo numérico que la spec) ──


def _config_3bp(**overrides) -> ScanConfig:
    base = dict(
        bp34_wrb_multiplicador_5m=2.0,
        bp34_tolerancia_pct_5m=0.25,
        bp34_n_invalidacion_5m=10,
        bp34_ventana_inicio_barras_5m=3,
        bp34_volumen_confirmado_mult=2.0,
        bp34_target_r_5m=0.5,  # target chico a propósito, para que el test lo alcance fácil
        slippage_bps=0.0,  # los tests de acá asumen fills perfectos, salvo los de slippage explícitos
    )
    base.update(overrides)
    return ScanConfig(**base)


def test_caminar_dia_detecta_entrada_y_la_resuelve_por_target(monkeypatch):
    # Sin parchear ATR ni volumen: el walker los calcula de forma incremental
    # (_ContextoIncremental). Con estas velas el ATR real de la barra 1 es ~1.12,
    # así que su rango de 8 supera de sobra el umbral (2 x ATR).
    base = datetime(2026, 1, 2, 9, 30)
    velas_dia = [
        _v(base, high=1.0, low=0.5, close=0.8),  # relleno — solo da contexto de 2 velas
        _v(base + timedelta(minutes=5), high=10.0, low=2.0, close=9.0),   # barra 1 (WRB, rango 8 = 2×ATR)
        _v(base + timedelta(minutes=10), high=9.0, low=6.0, close=8.0),   # barra 2, confirma grupo (pm=6)
        _v(base + timedelta(minutes=15), high=11.0, low=9.5, close=10.8, volume=250_000.0),  # gatillo, rompe 10 -> ENTRADA
        _v(base + timedelta(minutes=20), high=14.5, low=13.9, close=14.2),  # toca target (10 + 8×0.5=14)
    ]

    eventos = walker_3bp._caminar_dia(
        velas_dia, "AAPL", "5m", date(2026, 1, 2), _config_3bp(), FuenteDatos.HISTORICO
    )

    assert len(eventos) == 1
    ev = eventos[0]
    assert ev.ticker == "AAPL"
    assert ev.timeframe == "5m"
    assert ev.fuente == FuenteDatos.HISTORICO
    assert ev.tipo == "3BP"
    assert ev.tier == "confirmado"  # volumen del gatillo (250k) >= 2 × 100k
    assert ev.entry == 10.0
    assert ev.stop == 2.0
    assert ev.target == pytest.approx(14.0)
    assert ev.resultado == ResultadoBp34.TARGET
    assert ev.resultado_r == pytest.approx(0.5)


def _velas_escenario_3bp() -> list[Vela]:
    """Mismo escenario que test_caminar_dia_detecta_entrada_y_la_resuelve_por_target:
    entry=10, stop=2 (distancia 80% del precio), target chico que se toca."""
    base = datetime(2026, 1, 2, 9, 30)
    return [
        _v(base, high=1.0, low=0.5, close=0.8),
        _v(base + timedelta(minutes=5), high=10.0, low=2.0, close=9.0),
        _v(base + timedelta(minutes=10), high=9.0, low=6.0, close=8.0),
        _v(base + timedelta(minutes=15), high=11.0, low=9.5, close=10.8, volume=250_000.0),
        _v(base + timedelta(minutes=20), high=14.5, low=13.9, close=14.2),
    ]


def test_caminar_dia_descarta_entradas_con_stop_mas_corto_que_el_minimo(monkeypatch):
    # distancia al stop = (10 - 2) / 10 = 80% del precio
    eventos = walker_3bp._caminar_dia(
        _velas_escenario_3bp(), "AAPL", "5m", date(2026, 1, 2),
        _config_3bp(bp34_stop_min_pct=90.0), FuenteDatos.HISTORICO,
    )
    assert eventos == []


def test_caminar_dia_conserva_entradas_con_stop_igual_o_mayor_al_minimo(monkeypatch):
    eventos = walker_3bp._caminar_dia(
        _velas_escenario_3bp(), "AAPL", "5m", date(2026, 1, 2),
        _config_3bp(bp34_stop_min_pct=80.0), FuenteDatos.HISTORICO,  # justo en el borde: se conserva
    )
    assert len(eventos) == 1


def test_caminar_dia_aplica_el_slippage_de_la_config(monkeypatch):
    # target = 14, entry = 10, stop_dist = 8: costo = 0.001 * (14 + 10) / 8 = 0.003R
    eventos = walker_3bp._caminar_dia(
        _velas_escenario_3bp(), "AAPL", "5m", date(2026, 1, 2),
        _config_3bp(slippage_bps=10.0), FuenteDatos.HISTORICO,
    )
    assert eventos[0].resultado == ResultadoBp34.TARGET
    assert eventos[0].resultado_r == pytest.approx(0.5 - 0.003)


def test_caminar_dia_sin_patron_no_genera_eventos(monkeypatch):
    base = datetime(2026, 1, 2, 9, 30)
    velas_dia = [_v(base + timedelta(minutes=5 * i), high=1.0 + i * 0.01, low=0.9, close=0.95) for i in range(10)]

    eventos = walker_3bp._caminar_dia(velas_dia, "AAPL", "5m", date(2026, 1, 2), _config_3bp(), FuenteDatos.HISTORICO)
    assert eventos == []


# ── caminar_3bp — orquestación async, reseteo diario ────────────────────


def test_caminar_3bp_antes_del_piso_intraday_no_pide_nada(monkeypatch):
    llamado = False

    async def fake_get_history(*args, **kwargs):
        nonlocal llamado
        llamado = True
        return pl.DataFrame()

    monkeypatch.setattr(history_cache, "get_history", fake_get_history)

    eventos = asyncio.run(
        walker_3bp.caminar_3bp("AAPL", "5m", date(2023, 1, 1), date(2023, 1, 5), ScanConfig())
    )
    assert eventos == []
    assert llamado is False


def test_caminar_3bp_sin_historial_no_rompe(monkeypatch):
    async def fake_get_history(*args, **kwargs):
        raise RuntimeError("sin datos")

    monkeypatch.setattr(history_cache, "get_history", fake_get_history)

    eventos = asyncio.run(
        walker_3bp.caminar_3bp("XYZ", "5m", date(2026, 1, 2), date(2026, 1, 2), ScanConfig())
    )
    assert eventos == []


# ── sesión regular y ventana de detección ───────────────────────────────


def _df_velas(filas: list[tuple]) -> pl.DataFrame:
    """filas: (timestamp UTC naive, open, high, low, close, volume)"""
    return pl.DataFrame({
        "timestamp": [f[0] for f in filas],
        "open": [f[1] for f in filas], "high": [f[2] for f in filas], "low": [f[3] for f in filas],
        "close": [f[4] for f in filas], "volume": [f[5] for f in filas],
    }).with_columns(pl.col("timestamp").cast(pl.Datetime("ms")))


def test_filtrar_contexto_y_sesion_conserva_premarket_desde_las_4_y_descarta_lo_demas():
    # 2026-01-02 es EST (UTC-5): 4:00 NY = 09:00 UTC, 9:30 NY = 14:30 UTC, 16:00 NY = 21:00 UTC
    df = _df_velas([
        (datetime(2026, 1, 2, 5, 15), 1, 1, 1, 1, 1),    # 00:15 NY, madrugada -> fuera
        (datetime(2026, 1, 2, 8, 55), 1, 1, 1, 1, 1),    # 3:55 NY -> fuera
        (datetime(2026, 1, 2, 9, 0), 1, 1, 1, 1, 1),     # 4:00 NY, primera de pre-market -> dentro
        (datetime(2026, 1, 2, 14, 25), 1, 1, 1, 1, 1),   # 9:25 NY, pre-market -> dentro (contexto)
        (datetime(2026, 1, 2, 20, 55), 1, 1, 1, 1, 1),   # 15:55 NY, última de la sesión -> dentro
        (datetime(2026, 1, 2, 21, 0), 1, 1, 1, 1, 1),    # 16:00 NY, after-hours -> fuera
    ])
    res = walker_3bp._filtrar_contexto_y_sesion(df)
    assert res["timestamp"].to_list() == [
        datetime(2026, 1, 2, 9, 0), datetime(2026, 1, 2, 14, 25), datetime(2026, 1, 2, 20, 55),
    ]


def test_filtrar_contexto_y_sesion_respeta_el_horario_de_verano():
    # 2026-07-01 es EDT (UTC-4): 4:00 NY = 08:00 UTC — no 09:00
    df = _df_velas([
        (datetime(2026, 7, 1, 7, 55), 1, 1, 1, 1, 1),    # 3:55 NY -> fuera
        (datetime(2026, 7, 1, 8, 0), 1, 1, 1, 1, 1),     # 4:00 NY -> dentro
    ])
    assert walker_3bp._filtrar_contexto_y_sesion(df)["timestamp"].to_list() == [datetime(2026, 7, 1, 8, 0)]


# ── _ContextoIncremental: idéntico a las funciones que usa el stream ─────


def test_contexto_incremental_da_los_mismos_valores_que_las_funciones_del_stream():
    import random

    from src.trading_scanner.fetchers.market_data_cache import _atr14_de_velas, _volumen_promedio_de_velas

    rnd = random.Random(42)
    base = datetime(2026, 1, 2, 9, 30)
    velas, precio = [], 10.0
    for i in range(40):
        gap = rnd.uniform(-0.5, 0.5)
        abre = precio + gap
        cierra = abre + rnd.uniform(-0.6, 0.6)
        alto = max(abre, cierra) + rnd.uniform(0, 0.4)
        bajo = min(abre, cierra) - rnd.uniform(0, 0.4)
        velas.append(Vela(
            timestamp=base + timedelta(minutes=5 * i), open=abre, high=alto, low=bajo, close=cierra,
            volume=rnd.uniform(100, 5000),
        ))
        precio = cierra

    ctx = walker_3bp._ContextoIncremental()
    for i, vela in enumerate(velas):
        atr, vol = ctx.avanzar(vela)
        esperado_atr = _atr14_de_velas(velas[: i + 1])
        esperado_vol = _volumen_promedio_de_velas(velas[: i + 1])
        if esperado_atr is None:
            assert atr is None
        else:
            assert atr == pytest.approx(esperado_atr, rel=1e-9)
        if esperado_vol is None:
            assert vol is None
        else:
            assert vol == pytest.approx(esperado_vol, rel=1e-9)


def test_ventana_de_entradas_no_corta_el_seguimiento_de_una_entrada_ya_aceptada():
    velas = _velas_escenario_3bp()  # el gatillo es la barra de índice 3; el target se toca en la 4

    fuera = walker_3bp._caminar_dia(
        velas, "AAPL", "5m", date(2026, 1, 2), _config_3bp(), FuenteDatos.HISTORICO, entradas_hasta=3
    )
    assert fuera == []  # el gatillo (índice 3) queda fuera de la ventana [0, 3)

    dentro = walker_3bp._caminar_dia(
        velas, "AAPL", "5m", date(2026, 1, 2), _config_3bp(), FuenteDatos.HISTORICO, entradas_hasta=4
    )
    assert len(dentro) == 1
    # la barra 4 está fuera de la ventana de entradas pero sí sirve para resolver
    assert dentro[0].resultado == ResultadoBp34.TARGET


def test_entradas_anteriores_al_inicio_permitido_no_se_registran():
    velas = _velas_escenario_3bp()  # gatillo en el índice 3

    pre = walker_3bp._caminar_dia(
        velas, "AAPL", "5m", date(2026, 1, 2), _config_3bp(), FuenteDatos.HISTORICO, entradas_desde=4
    )
    assert pre == []  # el gatillo ocurre antes de entradas_desde: se descarta

    ok = walker_3bp._caminar_dia(
        velas, "AAPL", "5m", date(2026, 1, 2), _config_3bp(), FuenteDatos.HISTORICO, entradas_desde=3
    )
    assert len(ok) == 1


def _historial_con_patron_solo_en_premarket() -> pl.DataFrame:
    """El escenario 3BP completo a las 7:00-7:20 NY (12:00-12:20 UTC, EST),
    más velas planas de sesión regular que no forman ningún patrón."""
    pre = [
        (datetime(2026, 1, 2, 12, 0), 0.8, 1.0, 0.5, 0.8, 1000.0),
        (datetime(2026, 1, 2, 12, 5), 9.0, 10.0, 2.0, 9.0, 1000.0),
        (datetime(2026, 1, 2, 12, 10), 8.0, 9.0, 6.0, 8.0, 1000.0),
        (datetime(2026, 1, 2, 12, 15), 10.8, 11.0, 9.5, 10.8, 250_000.0),
        (datetime(2026, 1, 2, 12, 20), 14.2, 14.5, 13.9, 14.2, 1000.0),
    ]
    rth = [(datetime(2026, 1, 2, 14, 30 + 5 * i), 14.0, 14.1, 13.9, 14.0, 1000.0) for i in range(6)]
    return _df_velas(pre + rth)


def _caminar(monkeypatch, config: ScanConfig):
    async def fake_get_history(*args, **kwargs):
        return _historial_con_patron_solo_en_premarket()

    monkeypatch.setattr(history_cache, "get_history", fake_get_history)
    return asyncio.run(walker_3bp.caminar_3bp("AAPL", "5m", date(2026, 1, 2), date(2026, 1, 2), config))


def test_caminar_3bp_sin_filtro_de_sesion_detecta_el_patron_de_premarket(monkeypatch):
    assert len(_caminar(monkeypatch, _config_3bp())) == 1


def test_caminar_3bp_con_sesion_regular_ignora_el_patron_de_premarket(monkeypatch):
    assert _caminar(monkeypatch, _config_3bp(bp34_entradas_solo_sesion_regular=True)) == []


def test_el_contexto_de_premarket_habilita_la_barra_ancha_de_las_9_30():
    """Razón de alimentar el detector desde las 4:00: la WRB del patrón suele
    ser la propia barra de las 9:30 contra un ATR de pre-market chico. Sin
    esas barras de contexto el ATR arranca en el rango de la barra de
    apertura y el patrón no se detecta."""
    base = datetime(2026, 1, 2, 8, 0)
    premarket = [_v(base + timedelta(minutes=5 * i), high=10.05, low=9.95, close=10.0) for i in range(18)]
    apertura = datetime(2026, 1, 2, 9, 30)
    regular = [
        _v(apertura, high=12.0, low=10.0, close=11.8),                                  # barra 1: rango 2 (WRB)
        _v(apertura + timedelta(minutes=5), high=11.5, low=11.0, close=11.4),           # grupo
        _v(apertura + timedelta(minutes=10), high=12.4, low=11.3, close=12.3),          # gatillo, rompe 12
        _v(apertura + timedelta(minutes=15), high=13.5, low=12.3, close=13.2),          # toca el target (13)
    ]
    cfg = _config_3bp(bp34_entradas_solo_sesion_regular=True)

    con_contexto = walker_3bp._caminar_dia(
        premarket + regular, "AAPL", "5m", date(2026, 1, 2), cfg, FuenteDatos.HISTORICO,
        entradas_desde=len(premarket),
    )
    assert len(con_contexto) == 1
    assert con_contexto[0].entry == 12.0 and con_contexto[0].stop == 10.0

    solo_sesion = walker_3bp._caminar_dia(regular, "AAPL", "5m", date(2026, 1, 2), cfg, FuenteDatos.HISTORICO)
    assert solo_sesion == []
