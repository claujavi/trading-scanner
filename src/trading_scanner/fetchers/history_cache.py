import asyncio
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import polars as pl

from ..config import settings
from ..database import db
from . import schwab_history


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


def _filter_range(df: pl.DataFrame, start: date, end: date) -> pl.DataFrame:
    if df.is_empty():
        return df
    return df.filter(
        (pl.col("timestamp").dt.date() >= start)
        & (pl.col("timestamp").dt.date() <= end)
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
        return _filter_range(df, fecha_inicio, fecha_fin)

    # schwab_history.py siempre pide velas terminando en "ahora" (no acepta
    # una fecha de fin arbitraria) — si fecha_fin ya pasó, hay que pedir
    # suficientes períodos para que esa ventana (ahora → atrás) alcance a
    # cubrir fecha_inicio, no solo el largo del rango (fecha_fin - fecha_inicio).
    n_periods = _estimate_periods(timeframe, fecha_inicio, max(fecha_fin, date.today()))
    df = await schwab_history.get_history_async(ticker, timeframe, n_periods)
    if df.is_empty():
        return df

    await _save_partitions(ticker, timeframe, df)
    return _filter_range(df, fecha_inicio, fecha_fin)
