import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import polars as pl

from .schwab_client import get_client

Timeframe = Literal["5m", "15m", "4h", "d"]


def _compute_start_datetime(timeframe: Timeframe, n_periods: int) -> datetime:
    now = datetime.utcnow()
    if timeframe == "d":
        return now - timedelta(days=max(n_periods * 2, 5))
    if timeframe == "4h":
        return now - timedelta(hours=max(n_periods * 8, 48))
    if timeframe == "15m":
        return now - timedelta(minutes=max(n_periods * 15 * 2, 240))
    return now - timedelta(minutes=max(n_periods * 5 * 2, 120))


def _is_numeric_dtype(dtype: pl.DataType) -> bool:
    numeric_dtypes = {
        pl.Int8,
        pl.Int16,
        pl.Int32,
        pl.Int64,
        pl.UInt8,
        pl.UInt16,
        pl.UInt32,
        pl.UInt64,
        pl.Float16,
        pl.Float32,
        pl.Float64,
    }
    return dtype in numeric_dtypes


def _normalize_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    rename_map = {}
    if "datetime" in df.columns and "timestamp" not in df.columns:
        rename_map["datetime"] = "timestamp"
    if "date" in df.columns and "timestamp" not in df.columns:
        rename_map["date"] = "timestamp"

    if rename_map:
        df = df.rename(rename_map)

    if "timestamp" not in df.columns:
        raise RuntimeError("El historial no contiene columna de tiempo 'timestamp' o 'datetime'.")

    if _is_numeric_dtype(df["timestamp"].dtype):
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Int64).cast(pl.Datetime("ms"))
        )
    elif df["timestamp"].dtype == pl.Utf8:
        df = df.with_columns(
            pl.col("timestamp").str.strptime(pl.Datetime("ms"), fmt="%Y-%m-%dT%H:%M:%S%z", strict=False)
        )

    df = df.with_columns(
        pl.col("timestamp").alias("timestamp"),
    )

    column_map = {
        "openPrice": "open",
        "highPrice": "high",
        "lowPrice": "low",
        "closePrice": "close",
        "volume": "volume",
    }
    for source, target in column_map.items():
        if source in df.columns and target not in df.columns:
            df = df.rename({source: target})

    required_columns = {"timestamp", "open", "high", "low", "close", "volume"}
    if not required_columns.issubset(set(df.columns)):
        missing = required_columns - set(df.columns)
        raise RuntimeError(f"Historial recibido incompleto, faltan columnas: {sorted(missing)}")

    return df.select(["timestamp", "open", "high", "low", "close", "volume"])


def _parse_response(resp) -> pl.DataFrame:
    data = resp.json()
    if isinstance(data, dict):
        if "candles" in data and isinstance(data["candles"], list):
            records = data["candles"]
        else:
            records = []
            for value in data.values():
                if isinstance(value, dict) and "candles" in value:
                    records = value["candles"]
                    break
            if not records:
                if isinstance(data.get("symbols"), dict):
                    for value in data["symbols"].values():
                        if isinstance(value, dict) and "candles" in value:
                            records = value["candles"]
                            break
    elif isinstance(data, list):
        records = data
    else:
        records = []

    if not records:
        raise RuntimeError("No se pudo parsear el historial de Schwab: respuesta vacía")

    df = pl.from_dicts(records)
    return _normalize_dataframe(df)


def _resample_to_4h(df: pl.DataFrame) -> pl.DataFrame:
    df = df.sort("timestamp")
    df = df.with_columns(
        hour_block=(pl.col("timestamp").dt.hour() * 60 + pl.col("timestamp").dt.minute())
            .cast(pl.Int64)
    )
    df = df.with_columns(
        interval_start=(pl.col("timestamp").dt.truncate("4h"))
    )
    aggregated = (
        df.groupby("interval_start")
          .agg([
              pl.col("open").first().alias("open"),
              pl.col("high").max().alias("high"),
              pl.col("low").min().alias("low"),
              pl.col("close").last().alias("close"),
              pl.col("volume").sum().alias("volume"),
          ])
          .sort("interval_start")
    )
    return aggregated.rename({"interval_start": "timestamp"})


def _select_last_periods(df: pl.DataFrame, n_periods: int) -> pl.DataFrame:
    if df.height <= n_periods:
        return df
    return df.tail(n_periods)


def get_history(ticker: str, timeframe: Timeframe, n_periods: int) -> pl.DataFrame:
    client = get_client()
    if client is None:
        raise RuntimeError("No se pudo inicializar el cliente de Schwab")

    start_datetime = _compute_start_datetime(timeframe, n_periods)
    end_datetime = datetime.utcnow()

    if timeframe == "5m":
        resp = client.get_price_history_every_five_minutes(
            ticker,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            need_previous_close=False,
        )
    elif timeframe == "15m":
        resp = client.get_price_history_every_fifteen_minutes(
            ticker,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            need_previous_close=False,
        )
    elif timeframe == "d":
        resp = client.get_price_history_every_day(
            ticker,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            need_previous_close=False,
        )
    else:
        resp = client.get_price_history_every_fifteen_minutes(
            ticker,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            need_previous_close=False,
        )

    if resp.status_code != 200:
        raise RuntimeError(
            f"Error al descargar historial Schwab: {resp.status_code} {resp.text}"
        )

    df = _parse_response(resp)
    if timeframe == "4h":
        df = _resample_to_4h(df)

    df = _select_last_periods(df, n_periods)
    return df


async def get_history_async(ticker: str, timeframe: Timeframe, n_periods: int) -> pl.DataFrame:
    return await asyncio.to_thread(get_history, ticker, timeframe, n_periods)
