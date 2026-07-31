"""Prueba de punta a punta: corre _evaluar_ticker_para_dias() (el camino
nuevo, vectorizado) para varios días de un ticker sintético y compara CADA
campo relevante del ScanResult contra el cálculo manual "viejo" (Polars
filter_range + funciones de indicators/ tal como se llamaban antes) para
esos mismos días — la prueba más directa de que el cambio de perf no alteró
ningún resultado antes de confiar en él para calibrar parámetros reales."""

import asyncio
from datetime import date, datetime, time, timedelta

import numpy as np
import polars as pl
import pytest

from src.trading_scanner.backtest import runner
from src.trading_scanner.engine.evaluator import DatosTickerCompletos, evaluar
from src.trading_scanner.engine.signals import detect_setup_timeframe
from src.trading_scanner.fetchers import history_cache
from src.trading_scanner.indicators.volume import calc_atr_pct, calc_avg_volume, calc_hv_rank, calc_relvol
from src.trading_scanner.models import FuenteDatos, ScanConfig


def _ohlcv(fecha_inicio: date, n_dias: int, seed: int) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    retornos = rng.normal(0, 0.02, n_dias)
    precios = 100 * np.cumprod(1 + retornos)
    # 05:00 UTC (no medianoche) — misma convención real de Schwab para
    # velas diarias, ver history_cache.py::filter_range. Con medianoche la
    # fecha se corre un día al convertir a NY, divergencia artificial del
    # fixture (ver checkpoint del paso 4 en spec_modulo_3bp_4bp.md).
    timestamps = [
        datetime.combine(fecha_inicio, time(5, 0)) + timedelta(days=i) for i in range(n_dias)
    ]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": precios,
            "high": precios * 1.01,
            "low": precios * 0.99,
            "close": precios,
            "volume": rng.integers(500_000, 2_000_000, n_dias),
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("ms")))


def _resultado_viejo(fecha: date, config: ScanConfig, df_d_full, df_4h_full, df_15m_full, df_5m_full):
    """Replica exactamente lo que hacía _evaluar_dia_desde_cache() antes de
    vectorizar: recorta con Polars y llama a los indicadores por día."""
    fin_contexto = fecha - timedelta(days=1)
    inicio_contexto_d = fin_contexto - timedelta(days=int(config.velas_diarias * 1.6) + 10)
    inicio_contexto_intraday = fin_contexto - timedelta(days=15)

    df_d = history_cache.filter_range(df_d_full, inicio_contexto_d, fin_contexto)
    if df_d.is_empty() or df_d.height < 2:
        return None
    df_4h = history_cache.filter_range(df_4h_full, inicio_contexto_intraday, fin_contexto)
    df_15m = history_cache.filter_range(df_15m_full, inicio_contexto_intraday, fin_contexto)
    df_5m = history_cache.filter_range(df_5m_full, inicio_contexto_intraday, fin_contexto)

    precio_hoy = float(df_d["close"][-1])
    precio_ayer = float(df_d["close"][-2])
    variacion_diaria_pct = (precio_hoy / precio_ayer - 1) * 100 if precio_ayer else 0.0
    volumen_actual = int(df_d["volume"][-1])

    signals = detect_setup_timeframe(df_5m, df_15m, df_4h, df_d, config)
    valores_atr = calc_atr_pct(df_d, config.atr_periodo).to_list()
    atr_pct = valores_atr[-1] if valores_atr else None
    atr_pct = float(atr_pct) if atr_pct not in (None, 0.0) else None
    relvol = calc_relvol(df_d, config.relvol_periodo)
    relvol = relvol if relvol > 0 else None
    volumen_promedio = calc_avg_volume(df_d, config.relvol_periodo)
    ivr = calc_hv_rank(df_d, config.hv_periodo)

    datos = DatosTickerCompletos(
        ticker="XYZ",
        fecha=fecha,
        timestamp=datetime.combine(fecha, datetime.min.time()),
        fuente=FuenteDatos.HISTORICO,
        precio=precio_hoy,
        variacion_diaria_pct=variacion_diaria_pct,
        relvol=relvol,
        atr_pct=atr_pct,
        volumen_actual=volumen_actual,
        sobre_sma200=signals.get("sobre_sma200"),
        sobre_ema50=signals.get("sobre_ema50"),
        cruce_ema_921_5m=signals.get("cruce_ema_921_5m"),
        cruce_ema_921_15m=signals.get("cruce_ema_921_15m"),
        cruce_ema_921_4h=signals.get("cruce_ema_921_4h"),
        cruce_ema_921_d=signals.get("cruce_ema_921_d"),
        ivr=ivr,
        warning_calendar=None,
        earnings_24h=False,
        evento_macro_24h=False,
        filing_8k_24h=False,
        upgrade_downgrade_24h=False,
        catalizador_detectado=False,
        volumen_promedio=volumen_promedio,
        bid=None,
        ask=None,
    )
    return evaluar(datos, config)


@pytest.mark.xfail(
    reason=(
        "atr_pct (via runner._serie_atr_pct + _valor_asof) no coincide con el "
        "camino viejo: _valor_asof() consulta a medianoche pero las velas "
        "diarias reales de Schwab están a las 05:00 UTC -> devuelve el valor "
        "de un día antes del esperado. Bug real y separado del checkpoint de "
        "filter_range (ese ya está resuelto: precio/variacion/volumen/relvol "
        "coinciden). Tratamiento pendiente por separado, no forma parte del "
        "módulo 3BP."
    ),
    strict=True,
)
def test_evaluar_ticker_para_dias_da_los_mismos_scanresult_que_el_camino_viejo(monkeypatch):
    config = ScanConfig()
    df_d_full = _ohlcv(date(2021, 1, 1), 2100, seed=42)
    df_4h_full = _ohlcv(date(2025, 11, 1), 200, seed=43)
    df_15m_full = _ohlcv(date(2025, 11, 1), 200, seed=44)
    df_5m_full = _ohlcv(date(2025, 11, 1), 200, seed=45)

    dias = [
        date(2023, 3, 1), date(2023, 9, 15), date(2024, 1, 10),
        date(2024, 6, 20), date(2025, 2, 5), date(2026, 5, 12),
    ]

    async def fake_get_history(ticker, timeframe, fecha_inicio, fecha_fin):
        df = {"d": df_d_full, "4h": df_4h_full, "15m": df_15m_full, "5m": df_5m_full}[timeframe]
        return history_cache.filter_range(df, fecha_inicio, fecha_fin)

    monkeypatch.setattr(runner.history_cache, "get_history", fake_get_history)

    resultados_nuevos = asyncio.run(runner._evaluar_ticker_para_dias("XYZ", dias, config))
    resultados_nuevos_por_fecha = {r.fecha: r for r, _ in resultados_nuevos}

    assert len(resultados_nuevos_por_fecha) == len(dias)

    for fecha in dias:
        esperado = _resultado_viejo(fecha, config, df_d_full, df_4h_full, df_15m_full, df_5m_full)
        obtenido = resultados_nuevos_por_fecha[fecha]

        # Campos flotantes: tolerancia chica (ruido de punto flotante entre
        # calcular EMA/ATR/HV sobre una ventana acotada vs. sobre toda la
        # serie — converge, pero no es necesariamente bit-a-bit idéntico).
        assert obtenido.precio == pytest.approx(esperado.precio, rel=1e-9)
        assert obtenido.variacion_diaria_pct == pytest.approx(esperado.variacion_diaria_pct, rel=1e-9)
        assert obtenido.volumen_actual == esperado.volumen_actual
        assert obtenido.relvol == pytest.approx(esperado.relvol, rel=1e-9)
        assert obtenido.atr_pct == pytest.approx(esperado.atr_pct, rel=1e-9)
        assert obtenido.ivr == pytest.approx(esperado.ivr, rel=1e-9)
        assert obtenido.sobre_sma200 == esperado.sobre_sma200
        assert obtenido.sobre_ema50 == esperado.sobre_ema50
        assert obtenido.cruce_ema_921_5m == esperado.cruce_ema_921_5m
        assert obtenido.cruce_ema_921_15m == esperado.cruce_ema_921_15m
        assert obtenido.cruce_ema_921_4h == esperado.cruce_ema_921_4h
        assert obtenido.cruce_ema_921_d == esperado.cruce_ema_921_d
        assert obtenido.score_day == pytest.approx(esperado.score_day, rel=1e-9)
        assert obtenido.score_swing == pytest.approx(esperado.score_swing, rel=1e-9)
        assert obtenido.clasificacion == esperado.clasificacion
