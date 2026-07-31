"""filter_range() debe recortar por día de trading NY, no por fecha
calendario UTC cruda — ver checkpoint del paso 4 en
docs/spec_modulo_3bp_4bp.md (hallazgo confirmado con datos reales:
timestamps de Schwab son naive-pero-UTC, no NY)."""

from datetime import date, datetime, timedelta

import polars as pl

from src.trading_scanner.fetchers.history_cache import filter_range


def _df_horario(inicio_utc: datetime, horas: int) -> pl.DataFrame:
    """Una vela por hora (UTC, naive) — suficiente densidad para verificar
    límites de día con precisión sin depender de la granularidad real de
    5m/15m."""
    timestamps = [inicio_utc + timedelta(hours=i) for i in range(horas)]
    n = len(timestamps)
    return pl.DataFrame({
        "timestamp": timestamps,
        "open": [1.0] * n, "high": [1.0] * n, "low": [1.0] * n, "close": [1.0] * n,
        "volume": [100.0] * n,
    })


def _fechas_ny(df: pl.DataFrame) -> list[date]:
    ny = df["timestamp"].dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York")
    return ny.dt.date().unique().sort().to_list()


# ── EST (invierno, UTC-5) ────────────────────────────────────────────────


def test_filtra_por_dia_ny_en_invierno_est():
    # 3 días completos de velas horarias UTC, cruzando 2026-01-14/15/16.
    df = _df_horario(datetime(2026, 1, 14, 0, 0), 72)

    recorte = filter_range(df, date(2026, 1, 15), date(2026, 1, 15))

    assert _fechas_ny(recorte) == [date(2026, 1, 15)]
    # Un día completo en NY = 24 velas horarias, ni más ni menos.
    assert recorte.height == 24


def test_no_incluye_la_tarde_del_dia_anterior_en_est():
    """Caso concreto del bug original: la fecha UTC del 15/1 arranca a las
    00:00 UTC, que es 14/1 19:00 NY — sin la corrección, esas horas de la
    tarde/noche del 14 se colaban en el recorte del 15."""
    df = _df_horario(datetime(2026, 1, 14, 0, 0), 72)

    recorte = filter_range(df, date(2026, 1, 15), date(2026, 1, 15))
    ny = recorte["timestamp"].dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York")

    assert all(ts.date() == date(2026, 1, 15) for ts in ny.to_list())


# ── EDT (verano, UTC-4) ──────────────────────────────────────────────────


def test_filtra_por_dia_ny_en_verano_edt():
    df = _df_horario(datetime(2026, 7, 14, 0, 0), 72)

    recorte = filter_range(df, date(2026, 7, 15), date(2026, 7, 15))

    assert _fechas_ny(recorte) == [date(2026, 7, 15)]
    assert recorte.height == 24


# ── Transición de horario (caso límite) ─────────────────────────────────


def test_dia_completo_alrededor_de_transicion_a_edt_marzo_2026():
    """2026-03-08: EE.UU. adelanta el reloj (2am -> 3am, se salta una hora
    local). Pedir el día siguiente (ya en EDT) no debe romperse ni mezclar
    con el día de la transición."""
    df = _df_horario(datetime(2026, 3, 7, 0, 0), 96)  # cubre 7, 8, 9 y 10 de marzo UTC

    recorte = filter_range(df, date(2026, 3, 9), date(2026, 3, 9))

    assert _fechas_ny(recorte) == [date(2026, 3, 9)]
    assert recorte.height == 24  # día completo, ya establecido en EDT


def test_dia_completo_alrededor_de_transicion_a_est_noviembre_2026():
    """2026-11-01: EE.UU. atrasa el reloj (2am -> 1am, se repite una hora
    local). El día siguiente ya en EST debe recortarse limpio."""
    df = _df_horario(datetime(2026, 10, 31, 0, 0), 96)

    recorte = filter_range(df, date(2026, 11, 2), date(2026, 11, 2))

    assert _fechas_ny(recorte) == [date(2026, 11, 2)]
    assert recorte.height == 24


def test_rango_que_abarca_la_transicion_no_se_rompe():
    """Un rango multi-día que incluye el propio día de la transición no
    debe lanzar excepción ni perder/duplicar velas de forma inconsistente."""
    df = _df_horario(datetime(2026, 3, 6, 0, 0), 5 * 24)

    recorte = filter_range(df, date(2026, 3, 7), date(2026, 3, 9))

    fechas = _fechas_ny(recorte)
    assert fechas == [date(2026, 3, 7), date(2026, 3, 8), date(2026, 3, 9)]


# ── Casos borde ───────────────────────────────────────────────────────────


def test_df_vacio_no_rompe():
    vacio = pl.DataFrame(schema={
        "timestamp": pl.Datetime("ms"), "open": pl.Float64, "high": pl.Float64,
        "low": pl.Float64, "close": pl.Float64, "volume": pl.Float64,
    })
    assert filter_range(vacio, date(2026, 1, 1), date(2026, 1, 1)).is_empty()


def test_funciona_igual_si_el_timestamp_ya_viene_con_timezone():
    """Defensivo: si en algún momento el df ya llega con tz-info (en vez de
    naive-pero-UTC), filter_range no debe intentar replace_time_zone sobre
    algo que ya la tiene (rompería con "already has a timezone")."""
    df = _df_horario(datetime(2026, 1, 14, 0, 0), 72)
    df_tz = df.with_columns(pl.col("timestamp").dt.replace_time_zone("UTC"))

    recorte = filter_range(df_tz, date(2026, 1, 15), date(2026, 1, 15))

    assert recorte.height == 24
