import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import polars as pl

from ..config import settings
from ..database import db
from . import schwab_history

# Límite real de profundidad de historial de Schwab por timeframe, probado
# empíricamente el 2026-07-23 (ver CLAUDE.md, sección "Precarga masiva del
# cache"): diario llega a décadas atrás pero se acota a 2023 por practicidad
# (pedir más no aporta para calibrar y tarda minutos); intradía Schwab lo
# trunca en silencio antes de esa fecha sin importar qué tan atrás se pida.
TIMEFRAMES = ("d", "4h", "15m", "5m")
FECHA_INICIO_DEFAULT: dict[str, date] = {
    "d": date(2023, 1, 1),
    "4h": date(2025, 11, 1),
    "15m": date(2025, 11, 1),
    "5m": date(2025, 11, 1),
}


def _month_list(start: date, end: date) -> list[Tuple[int, int]]:
    current = date(start.year, start.month, 1)
    months = []
    while current <= end:
        months.append((current.year, current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def _estimate_periods(timeframe: str, start: date, end: date) -> int:
    days = max((end - start).days + 1, 1)
    if timeframe == "d":
        return days + 2
    if timeframe == "4h":
        return max(int(days * 6), 10)
    if timeframe == "15m":
        return max(int(days * 24 * 4), 100)
    return max(int(days * 24 * 12), 100)


def filter_range(df: pl.DataFrame, start: date, end: date) -> pl.DataFrame:
    """`start`/`end` son fechas de trading NY (calendario del mercado, no
    UTC). Los timestamps que llegan de Schwab son naive pero representan
    un instante UTC (epoch ms casteado directo, ver
    schwab_history._parse_response) — filtrar por `.dt.date()` directo
    sobre eso compara contra la fecha calendario UTC, no la NY, y para
    velas intradía (5m/15m/4h) eso corre la ventana ~4-5 horas según la
    época del año (EST/EDT): un pedido de "el día X" termina devolviendo
    la tarde/noche del día X-1 más la mañana del día X, no el día X
    completo. Confirmado con datos reales — ver docs/spec_modulo_3bp_4bp.md,
    sección 7 (hallazgo original) y "Checkpoint del paso 4" (confirmación
    y fix). Para velas diarias esto no se notaba en la práctica porque el
    timestamp diario de Schwab cae casualmente en la misma fecha NY que
    UTC — coincidencia frágil, no una garantía, así que se convierte acá
    también en vez de dejarlo como caso especial."""
    if df.is_empty():
        return df
    ts = df["timestamp"]
    ts_ny = ts.dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York") if ts.dtype.time_zone is None else ts.dt.convert_time_zone("America/New_York")
    return df.filter(
        (ts_ny.dt.date() >= start)
        & (ts_ny.dt.date() <= end)
    )


async def _read_parquet(path: Path) -> pl.DataFrame:
    return await asyncio.to_thread(pl.read_parquet, path)


async def _write_parquet(path: Path, df: pl.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(df.write_parquet, path)


async def _save_partitions(ticker: str, timeframe: str, df: pl.DataFrame) -> None:
    df = df.with_columns(
        year=pl.col("timestamp").dt.year(),
        month=pl.col("timestamp").dt.month(),
    )
    for year, month in df.select([pl.col("year"), pl.col("month")]).unique().iter_rows():
        partition = df.filter((pl.col("year") == year) & (pl.col("month") == month))
        partition = partition.drop(["year", "month"]).sort("timestamp")
        path = (
            settings.backtest_data_path
            / ticker
            / timeframe
            / str(year)
            / f"{month:02}.parquet"
        )
        await _write_parquet(path, partition)

        fecha_inicio = partition.select(pl.col("timestamp").min()).item().strftime("%Y-%m-%d")
        fecha_fin = partition.select(pl.col("timestamp").max()).item().strftime("%Y-%m-%d")
        await db.upsert_history_cache_meta(
            ticker=ticker,
            timeframe=timeframe,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            archivo=str(path),
        )


def esta_cacheado(ticker: str, timeframe: str, fecha_inicio: date, fecha_fin: date) -> bool:
    """True si TODOS los meses del rango ya tienen Parquet — o sea,
    get_history() no va a tocar la red para este pedido. Usado por
    cli_precarga.py para no pausar entre pedidos que ya estaban cacheados
    (solo hace falta el ritmo de espera cuando sí se golpea Schwab)."""
    partition_root = settings.backtest_data_path / ticker / timeframe
    return all(
        (partition_root / str(year) / f"{month:02}.parquet").exists()
        for year, month in _month_list(fecha_inicio, fecha_fin)
    )


_ESQUEMA_VACIO = {
    "timestamp": pl.Datetime("ms"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64,
}


async def _marcar_meses_sin_datos(
    ticker: str, timeframe: str, fecha_inicio: date, fecha_fin: date, df: pl.DataFrame
) -> None:
    """Cuando Schwab confirma (con una respuesta válida, no un error) que no
    tiene velas para algún mes del rango pedido —instrumento recién listado
    (meses antes del primero real), o un mes puntual sin operaciones en medio
    del rango (ticker ilíquido, halt de trading)—, guarda un Parquet vacío
    para ese mes. Sin esto, `esta_cacheado()`/`get_history()` (que solo miran
    si el archivo existe, no si Schwab realmente tenía datos) volverían a
    golpear la red en vano cada vez que se pida ese mismo rango — en un
    backtest/optimizador que evalúa el mismo rango en cada trial, eso es una
    llamada de red repetida e innecesaria por trial.

    Nunca marca el mes en curso — ese lo mantiene al día
    `actualizar_hasta_hoy()` en cada scan en vivo, y podría tener datos
    parciales todavía (no confirmado como "sin operaciones", solo que el día
    de hoy no cerró aún)."""
    mes_actual = (date.today().year, date.today().month)
    meses_presentes = set(
        df.select(
            year=pl.col("timestamp").dt.year(), month=pl.col("timestamp").dt.month()
        ).unique().iter_rows()
    )
    vacio = pl.DataFrame(schema=_ESQUEMA_VACIO)
    for year, month in _month_list(fecha_inicio, fecha_fin):
        if (year, month) in meses_presentes or (year, month) == mes_actual:
            continue
        path = settings.backtest_data_path / ticker / timeframe / str(year) / f"{month:02}.parquet"
        if not path.exists():
            await _write_parquet(path, vacio)


async def get_history(
    ticker: str,
    timeframe: str,
    fecha_inicio: date,
    fecha_fin: date,
) -> pl.DataFrame:
    partition_root = settings.backtest_data_path / ticker / timeframe
    months = _month_list(fecha_inicio, fecha_fin)
    paths: List[Path] = []
    missing = False

    for year, month in months:
        path = partition_root / str(year) / f"{month:02}.parquet"
        if not path.exists():
            missing = True
            break
        paths.append(path)

    if not missing and paths:
        dfs = [await _read_parquet(path) for path in paths]
        df = pl.concat(dfs, how="vertical").sort("timestamp")
        return filter_range(df, fecha_inicio, fecha_fin)

    # schwab_history.py siempre pide velas terminando en "ahora" (no acepta
    # una fecha de fin arbitraria) — si fecha_fin ya pasó, hay que pedir
    # suficientes períodos para que esa ventana (ahora → atrás) alcance a
    # cubrir fecha_inicio, no solo el largo del rango (fecha_fin - fecha_inicio).
    n_periods = _estimate_periods(timeframe, fecha_inicio, max(fecha_fin, date.today()))
    df = await schwab_history.get_history_async(ticker, timeframe, n_periods)
    if df.is_empty():
        return df

    await _save_partitions(ticker, timeframe, df)
    await _marcar_meses_sin_datos(ticker, timeframe, fecha_inicio, fecha_fin, df)

    return filter_range(df, fecha_inicio, fecha_fin)


async def actualizar_hasta_hoy(ticker: str, timeframe: str) -> None:
    """Mantiene backtest_data/ al día para un ticker que salió hoy en el scan
    en vivo, llamado desde pipeline.py en cada scan (no solo desde
    cli_precarga.py bajo demanda).

    Un mes ya cacheado no garantiza que tenga la vela de hoy —esta_cacheado()
    solo confirma que el archivo existe, no que esté completo hasta la fecha—
    así que no alcanza con el chequeo de siempre. Dos casos:
    - Ticker nunca visto en este timeframe: backfill completo desde el
      límite real de Schwab (FECHA_INICIO_DEFAULT).
    - Ticker ya conocido: refresca solo el mes en curso (1 sola llamada a
      Schwab, liviana) sin tocar los meses anteriores ya cerrados.

    Puede lanzar (red, 429, ticker sin datos) — quien llame desde el scan en
    vivo (pipeline.py) debe atajar la excepción ahí, con el mismo criterio
    que ya usa para el resto del historial: un fallo acá no debe tumbar el
    scan del día."""
    hoy = date.today()
    root = settings.backtest_data_path / ticker / timeframe
    if not root.exists():
        await get_history(ticker, timeframe, FECHA_INICIO_DEFAULT[timeframe], hoy)
        return

    inicio_mes = date(hoy.year, hoy.month, 1)
    n_periods = _estimate_periods(timeframe, inicio_mes, hoy)
    df = await schwab_history.get_history_async(ticker, timeframe, n_periods)
    if df.is_empty():
        return
    await _save_partitions(ticker, timeframe, df)


def tickers_cacheados(timeframe: str = "d") -> list[str]:
    """Tickers que ya tienen al menos un Parquet cacheado para ese timeframe
    en backtest_data/ — usado por el optimizador (universo curado) para no
    obligar a elegir tickers a mano si ya hay historial descargado de
    corridas anteriores."""
    root = settings.backtest_data_path
    if not root.exists():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and any((p / timeframe).glob("*/*.parquet"))
    )


def rango_cacheado(timeframe: str = "d") -> Optional[Tuple[date, date]]:
    """Rango (mes más antiguo, mes más reciente) cubierto por los Parquet
    cacheados de ese timeframe, leído de los nombres de carpeta/archivo
    (year/month.parquet) — no abre los archivos, es solo para mostrar al
    usuario qué rango no va a disparar descargas nuevas a Schwab."""
    root = settings.backtest_data_path
    if not root.exists():
        return None

    meses = [
        (int(p.parent.name), int(p.stem))
        for p in root.glob(f"*/{timeframe}/*/*.parquet")
    ]
    if not meses:
        return None

    meses.sort()
    year_min, month_min = meses[0]
    year_max, month_max = meses[-1]

    fecha_inicio = date(year_min, month_min, 1)
    if month_max == 12:
        fecha_fin = date(year_max, 12, 31)
    else:
        fecha_fin = date(year_max, month_max + 1, 1) - timedelta(days=1)
    return fecha_inicio, fecha_fin
