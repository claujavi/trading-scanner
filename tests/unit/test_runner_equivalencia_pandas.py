"""Verifica que el recorte por pandas pre-convertido (runner._a_pandas_indexado
+ runner._recortar_pandas) da EXACTAMENTE los mismos resultados que el camino
viejo (history_cache.filter_range sobre Polars, re-convertido a pandas en cada
llamada de indicador) — el cambio de perf no debe alterar ningún valor."""

from datetime import date, datetime, time, timedelta

import numpy as np
import polars as pl
import pytest

from src.trading_scanner.backtest import runner
from src.trading_scanner.fetchers import history_cache
from src.trading_scanner.indicators.trend import calc_ema, calc_sma, detect_cruce_ema
from src.trading_scanner.indicators.volume import calc_atr_pct, calc_avg_volume, calc_hv_rank, calc_relvol
from src.trading_scanner.models import ScanConfig


def _ohlcv_realista(fecha_inicio: date, n_dias: int, seed: int) -> pl.DataFrame:
    """Precios con algo de variación (no constante) para que EMA/ATR/HV rank
    den valores no triviales — una serie perfectamente plana esconde bugs de
    ventana porque casi cualquier cálculo da 0 o None igual."""
    rng = np.random.default_rng(seed)
    n = n_dias
    retornos = rng.normal(0, 0.02, n)
    precios = 100 * np.cumprod(1 + retornos)
    # 05:00 UTC (no medianoche) — misma convención que las velas diarias
    # reales de Schwab (verificado empíricamente, ver history_cache.py::
    # filter_range), donde la fecha UTC coincide con la fecha NY tanto en
    # EST como en EDT. Con medianoche UTC, la fecha se corre un día hacia
    # atrás al convertir a NY — divergencia artificial de los fixtures,
    # no un bug real (ver checkpoint del paso 4 en spec_modulo_3bp_4bp.md).
    timestamps = [
        datetime.combine(fecha_inicio, time(5, 0)) + timedelta(days=i) for i in range(n)
    ]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": precios,
            "high": precios * 1.01,
            "low": precios * 0.99,
            "close": precios,
            "volume": rng.integers(500_000, 2_000_000, n),
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("ms")))


def test_recorte_pandas_da_los_mismos_indicadores_que_filter_range_polars():
    """relvol/avg_volume/hv_rank son las únicas funciones que hoy consumen
    _recortar_pandas() (ver runner._evaluar_dia_desde_cache) — cruce_ema y
    atr_pct se vectorizaron aparte (_serie_*) y ya no pasan por acá, así que
    no se comparan en este test (ver test_serie_*_vectorizada_coincide_con_*
    más abajo)."""
    config = ScanConfig()
    df_d_full = _ohlcv_realista(date(2023, 1, 1), 700, seed=1)

    fecha = date(2024, 8, 15)  # bien adentro del rango, con contexto de sobra
    fin_contexto = fecha - timedelta(days=1)
    inicio_contexto_d = fin_contexto - timedelta(days=int(config.velas_diarias * 1.6) + 10)

    # --- Camino viejo: Polars filter_range, indicadores re-convierten cada vez ---
    df_d_polars = history_cache.filter_range(df_d_full, inicio_contexto_d, fin_contexto)
    relvol_viejo = calc_relvol(df_d_polars, config.relvol_periodo)
    vol_prom_viejo = calc_avg_volume(df_d_polars, config.relvol_periodo)
    hv_viejo = calc_hv_rank(df_d_polars, config.hv_periodo)

    # --- Camino nuevo: pandas pre-convertido + recorte pandas ---
    pdf_d_full = runner._a_pandas_indexado(df_d_full)
    df_d_pandas = runner._recortar_pandas(pdf_d_full, inicio_contexto_d, fin_contexto)

    relvol_nuevo = calc_relvol(df_d_pandas, config.relvol_periodo)
    vol_prom_nuevo = calc_avg_volume(df_d_pandas, config.relvol_periodo)
    hv_nuevo = calc_hv_rank(df_d_pandas, config.hv_periodo)

    # Mismo tamaño de ventana en ambos caminos — condición necesaria para que
    # HV rank (rankea contra TODO lo que se le pase) dé lo mismo.
    assert len(df_d_polars) == len(df_d_pandas)

    assert relvol_viejo == relvol_nuevo
    assert vol_prom_viejo == vol_prom_nuevo
    assert hv_viejo == hv_nuevo


def test_recorte_pandas_da_mismo_precio_y_volumen_que_polars():
    df_d_full = _ohlcv_realista(date(2023, 1, 1), 700, seed=5)
    fecha = date(2024, 6, 1)
    fin_contexto = fecha - timedelta(days=1)
    inicio_contexto_d = fin_contexto - timedelta(days=400)

    df_polars = history_cache.filter_range(df_d_full, inicio_contexto_d, fin_contexto)
    pdf_full = runner._a_pandas_indexado(df_d_full)
    df_pandas = runner._recortar_pandas(pdf_full, inicio_contexto_d, fin_contexto)

    assert float(df_polars["close"][-1]) == float(df_pandas["close"].iloc[-1])
    assert float(df_polars["close"][-2]) == float(df_pandas["close"].iloc[-2])
    assert int(df_polars["volume"][-1]) == int(df_pandas["volume"].iloc[-1])
    assert len(df_polars) == len(df_pandas)


_DIAS_DE_PRUEBA = [date(2023, 6, 1), date(2024, 3, 15), date(2025, 1, 10), date(2026, 5, 20)]


@pytest.mark.parametrize("fecha", _DIAS_DE_PRUEBA)
def test_serie_cruce_ema_vectorizada_coincide_con_detect_cruce_ema_por_dia(fecha):
    config = ScanConfig()
    df_d_full = _ohlcv_realista(date(2021, 1, 1), 2100, seed=10)

    fin_contexto = fecha - timedelta(days=1)
    inicio_contexto_d = fin_contexto - timedelta(days=int(config.velas_diarias * 1.6) + 10)

    df_polars = history_cache.filter_range(df_d_full, inicio_contexto_d, fin_contexto)
    esperado = detect_cruce_ema(df_polars, config.ema_rapida, config.ema_media)

    pdf_full = runner._a_pandas_indexado(df_d_full)
    serie = runner._serie_cruce_ema(pdf_full, config.ema_rapida, config.ema_media)
    obtenido = runner._valor_asof(serie, fin_contexto)

    assert obtenido == esperado


@pytest.mark.parametrize("fecha", _DIAS_DE_PRUEBA)
def test_serie_sobre_ma_vectorizada_coincide_con_above_ma_por_dia(fecha):
    config = ScanConfig()
    df_d_full = _ohlcv_realista(date(2021, 1, 1), 2100, seed=11)

    fin_contexto = fecha - timedelta(days=1)
    inicio_contexto_d = fin_contexto - timedelta(days=int(config.velas_diarias * 1.6) + 10)

    df_polars = history_cache.filter_range(df_d_full, inicio_contexto_d, fin_contexto)

    for periodo, use_ema in [(config.sma_tendencia, False), (config.ema_lenta, True)]:
        serie_ma = calc_ema(df_polars, periodo) if use_ema else calc_sma(df_polars, periodo)
        esperado = float(df_polars["close"][-1]) > float(serie_ma.to_list()[-1])

        pdf_full = runner._a_pandas_indexado(df_d_full)
        serie = runner._serie_sobre_ma(pdf_full, periodo, use_ema)
        obtenido = runner._valor_asof(serie, fin_contexto)

        assert bool(obtenido) == esperado


@pytest.mark.parametrize("fecha", _DIAS_DE_PRUEBA)
def test_serie_atr_pct_vectorizada_coincide_con_calc_atr_pct_por_dia(fecha):
    config = ScanConfig()
    df_d_full = _ohlcv_realista(date(2021, 1, 1), 2100, seed=12)

    fin_contexto = fecha - timedelta(days=1)
    inicio_contexto_d = fin_contexto - timedelta(days=int(config.velas_diarias * 1.6) + 10)

    df_polars = history_cache.filter_range(df_d_full, inicio_contexto_d, fin_contexto)
    esperado = calc_atr_pct(df_polars, config.atr_periodo).to_list()[-1]

    pdf_full = runner._a_pandas_indexado(df_d_full)
    serie = runner._serie_atr_pct(pdf_full, config.atr_periodo)
    obtenido = runner._valor_asof(serie, fin_contexto)

    assert obtenido == pytest.approx(esperado, rel=1e-9)
