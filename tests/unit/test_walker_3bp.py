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
    # ATR fijo (mismo criterio que test_pattern_3bp.py) — evita depender de
    # que calc_atr converja con pocas velas sintéticas. Contexto < 2 velas
    # -> None (mismo umbral que _atr14_de_velas real, ver market_data_cache.py).
    monkeypatch.setattr(walker_3bp, "_atr14_de_velas", lambda velas: 4.0 if len(velas) >= 2 else None)
    monkeypatch.setattr(walker_3bp, "_volumen_promedio_de_velas", lambda velas: 100_000.0)

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


def _fijar_contexto(monkeypatch):
    monkeypatch.setattr(walker_3bp, "_atr14_de_velas", lambda velas: 4.0 if len(velas) >= 2 else None)
    monkeypatch.setattr(walker_3bp, "_volumen_promedio_de_velas", lambda velas: 100_000.0)


def test_caminar_dia_descarta_entradas_con_stop_mas_corto_que_el_minimo(monkeypatch):
    _fijar_contexto(monkeypatch)
    # distancia al stop = (10 - 2) / 10 = 80% del precio
    eventos = walker_3bp._caminar_dia(
        _velas_escenario_3bp(), "AAPL", "5m", date(2026, 1, 2),
        _config_3bp(bp34_stop_min_pct=90.0), FuenteDatos.HISTORICO,
    )
    assert eventos == []


def test_caminar_dia_conserva_entradas_con_stop_igual_o_mayor_al_minimo(monkeypatch):
    _fijar_contexto(monkeypatch)
    eventos = walker_3bp._caminar_dia(
        _velas_escenario_3bp(), "AAPL", "5m", date(2026, 1, 2),
        _config_3bp(bp34_stop_min_pct=80.0), FuenteDatos.HISTORICO,  # justo en el borde: se conserva
    )
    assert len(eventos) == 1


def test_caminar_dia_aplica_el_slippage_de_la_config(monkeypatch):
    _fijar_contexto(monkeypatch)
    # target = 14, entry = 10, stop_dist = 8: costo = 0.001 * (14 + 10) / 8 = 0.003R
    eventos = walker_3bp._caminar_dia(
        _velas_escenario_3bp(), "AAPL", "5m", date(2026, 1, 2),
        _config_3bp(slippage_bps=10.0), FuenteDatos.HISTORICO,
    )
    assert eventos[0].resultado == ResultadoBp34.TARGET
    assert eventos[0].resultado_r == pytest.approx(0.5 - 0.003)


def test_caminar_dia_sin_patron_no_genera_eventos(monkeypatch):
    monkeypatch.setattr(walker_3bp, "_atr14_de_velas", lambda velas: 4.0 if len(velas) >= 2 else None)
    monkeypatch.setattr(walker_3bp, "_volumen_promedio_de_velas", lambda velas: 100_000.0)

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
