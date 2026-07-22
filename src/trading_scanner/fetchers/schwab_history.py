import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Optional

import polars as pl

from ..database import db
from .schwab_client import get_client

Timeframe = Literal["5m", "15m", "4h", "d"]

# Cache negativo: cuando Schwab confirma que no tiene historial para un
# ticker/timeframe (SPACs recién listados, warrants, preferred shares OTC,
# etc. — "basura" para este sistema, no un error transitorio), se registra
# acá para no volver a golpear a Schwab por lo mismo. Es el único choke
# point que llaman tanto pipeline.py (scan en vivo) como history_cache.py
# (backtest/optimizador) — un solo cache sirve a los dos casos.
#
# TTL de 30 días (no permanente): Schwab podría agregar cobertura de un
# instrumento más adelante, y no hay forma de saberlo sin volver a intentar
# de vez en cuando.
_TTL_SIN_HISTORIAL = timedelta(days=30)
_sin_historial_cache: Optional[dict[tuple[str, str], datetime]] = None


async def _cargar_sin_historial_cache() -> dict[tuple[str, str], datetime]:
    global _sin_historial_cache
    if _sin_historial_cache is None:
        filas = await db.get_tickers_sin_historial()
        _sin_historial_cache = {
            (f["ticker"], f["timeframe"]): datetime.fromisoformat(f["verificado_en"])
            for f in filas
        }
    return _sin_historial_cache


async def _tiene_historial_confirmado_vacio(ticker: str, timeframe: str) -> bool:
    cache = await _cargar_sin_historial_cache()
    verificado_en = cache.get((ticker, timeframe))
    if verificado_en is None:
        return False
    return (datetime.utcnow() - verificado_en) < _TTL_SIN_HISTORIAL


async def _marcar_sin_historial(ticker: str, timeframe: str, motivo: str) -> None:
    cache = await _cargar_sin_historial_cache()
    cache[(ticker, timeframe)] = datetime.utcnow()
    await db.marcar_ticker_sin_historial(ticker, timeframe, motivo)


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
        df.group_by("interval_start")
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


_MOTIVO_SIN_DATOS = "No se pudo parsear el historial de Schwab: respuesta vacía"


async def get_history_async(ticker: str, timeframe: Timeframe, n_periods: int) -> pl.DataFrame:
    if await _tiene_historial_confirmado_vacio(ticker, timeframe):
        raise RuntimeError(
            f"Sin historial confirmado para {ticker} ({timeframe}) — Schwab no cubre "
            "este instrumento (cache negativo, ver tickers_sin_historial)."
        )

    try:
        return await asyncio.to_thread(get_history, ticker, timeframe, n_periods)
    except RuntimeError as exc:
        # Solo cachear la falla "definitiva" (respuesta sin velas en absoluto) —
        # otros RuntimeError (cliente sin inicializar, HTTP 5xx) pueden ser
        # transitorios y no deben blacklistear el ticker permanentemente.
        if _MOTIVO_SIN_DATOS in str(exc):
            await _marcar_sin_historial(ticker, timeframe, str(exc))
        raise
