"""
market_data_cache.py — estado en memoria de cada ticker suscrito al stream
de sesión (Sprint 2). Nunca persiste a Turso durante la sesión — la
persistencia ocurre solo cuando un evento significativo dispara evaluar()
(ver schwab_stream.py / main.py), igual que documenta CLAUDE.md.

Separación de responsabilidades entre los dos puntos de entrada:

- actualizar_tick() — quotes de alta frecuencia (level_one_equity): precio,
  bid/ask, volumen acumulado. Detecta cruce de VWAP, cambio de categoría de
  RelVol y nuevo máximo/mínimo del día. Nunca recalcula EMA: hacerlo en
  cada quote sería caro y, sobre todo, semánticamente incorrecto — la EMA
  9/21 del resto del sistema opera sobre velas de 5m, no sobre el precio
  instantáneo.
- actualizar_vela_1m() — velas de 1 minuto (chart_equity): se bucketean en
  velas de 5m. Solo al cerrarse una ventana de 5m se recalcula
  detect_cruce_ema() (ya existente en indicators/trend.py) y se compara
  contra el valor guardado para detectar el cruce fresco — detect_cruce_ema
  devuelve la posición relativa actual, no un evento, así que el "cruce"
  como tal solo existe acá, comparando snapshot contra snapshot.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

import polars as pl

from ..engine.evaluator import DatosTickerCompletos
from ..fetchers.calendar_client import CalendarWarning
from ..indicators.trend import detect_cruce_ema
from ..models import FuenteDatos, ScanConfig, TickerBasico

_EMPTY_DF = pl.DataFrame(schema={
    "timestamp": pl.Datetime("ms"),
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
})


@dataclass
class Vela:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TickerCache:
    ticker: str

    # ── Contexto sembrado una vez en pre-market — no se actualiza en vivo ──
    ticker_data: Optional[TickerBasico] = None
    df_15m: pl.DataFrame = field(default_factory=lambda: _EMPTY_DF)
    df_4h: pl.DataFrame = field(default_factory=lambda: _EMPTY_DF)
    df_d: pl.DataFrame = field(default_factory=lambda: _EMPTY_DF)
    volumen_promedio: Optional[float] = None
    atr_pct: Optional[float] = None
    ivr: Optional[float] = None
    sobre_sma200: Optional[bool] = None
    sobre_ema50: Optional[bool] = None
    cruce_ema_921_15m: Optional[bool] = None
    cruce_ema_921_4h: Optional[bool] = None
    cruce_ema_921_d: Optional[bool] = None
    warning: Optional[CalendarWarning] = None

    # ── Estado en vivo, actualizado tick a tick ─────────────────────────────
    ultimo_precio: float = 0.0
    bid: Optional[float] = None
    ask: Optional[float] = None
    volumen_acumulado: float = 0.0
    _cum_pv: float = 0.0
    _cum_v: float = 0.0
    vwap: Optional[float] = None
    sobre_vwap: Optional[bool] = None
    max_dia: Optional[float] = None
    min_dia: Optional[float] = None
    relvol_categoria: Optional[str] = None  # "BAJO" | "SWING" | "DAY"
    cruce_ema_921_5m: Optional[bool] = None

    # velas de 5m: seedeadas con el historial pre-market (para que la EMA
    # tenga contexto, no arranque de cero al abrir el mercado) + las nuevas
    # que se van cerrando durante la sesión
    velas_hoy: list[Vela] = field(default_factory=list)

    # ── Última evaluación disparada por un evento significativo ─────────────
    ultimo_score_day: float = 0.0
    ultimo_score_swing: float = 0.0
    ultima_clasificacion: Optional[str] = None
    ultima_evaluacion: Optional[datetime] = None
    suscrito_en: Optional[datetime] = None

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def _df_a_velas(df: pl.DataFrame) -> list[Vela]:
    if df is None or df.is_empty():
        return []
    velas = []
    for row in df.iter_rows(named=True):
        velas.append(Vela(
            timestamp=row["timestamp"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        ))
    return velas


def _velas_a_df(velas: list[Vela]) -> pl.DataFrame:
    if not velas:
        return _EMPTY_DF
    return pl.DataFrame({
        "timestamp": [v.timestamp for v in velas],
        "open": [v.open for v in velas],
        "high": [v.high for v in velas],
        "low": [v.low for v in velas],
        "close": [v.close for v in velas],
        "volume": [v.volume for v in velas],
    })


def _floor_5min(ts: datetime) -> datetime:
    minuto = (ts.minute // 5) * 5
    return ts.replace(minute=minuto, second=0, microsecond=0)


def _categoria_relvol(relvol: Optional[float], config: ScanConfig) -> Optional[str]:
    if relvol is None:
        return None
    if relvol >= config.relvol_umbral_day:
        return "DAY"
    if relvol >= config.relvol_umbral_swing_min:
        return "SWING"
    return "BAJO"


class MarketDataCache:
    """Dict en memoria {ticker: TickerCache}. Nunca persiste a Turso —
    la config se recibe una sola vez al construir (no se re-lee de Turso
    en cada tick; si el usuario cambia /config a mitad de sesión, el
    cache sigue con la config vigente al momento de arrancar el stream,
    consistente con que la config activa ya se fija por scan/proceso)."""

    def __init__(self, config: ScanConfig):
        self._config = config
        self._tickers: dict[str, TickerCache] = {}

    def tiene(self, ticker: str) -> bool:
        return ticker in self._tickers

    def tickers_suscritos(self) -> list[str]:
        return list(self._tickers.keys())

    def get(self, ticker: str) -> Optional[TickerCache]:
        return self._tickers.get(ticker)

    def eliminar(self, ticker: str) -> bool:
        """Saca un ticker del cache — usado cuando Schwab no tiene datos
        para el símbolo (ej. acciones preferidas/ADRs con formato raro del
        CSV de ToS) y no tiene sentido seguir intentando actualizarlo."""
        return self._tickers.pop(ticker, None) is not None

    def _relvol_actual(self, cache: TickerCache) -> Optional[float]:
        if not cache.volumen_promedio:
            return None
        return cache.volumen_acumulado / cache.volumen_promedio

    def seed(
        self,
        ticker_data: TickerBasico,
        df_5m: pl.DataFrame,
        df_15m: pl.DataFrame,
        df_4h: pl.DataFrame,
        df_d: pl.DataFrame,
        signals: dict,
        volumen_promedio: Optional[float],
        atr_pct: Optional[float],
        ivr: Optional[float],
        warning: CalendarWarning,
    ) -> None:
        """Siembra el cache con lo que process_ticker() ya trajo del
        pipeline pre-market — no dispara ninguna llamada de red nueva."""
        ticker = ticker_data.ticker
        cache = TickerCache(
            ticker=ticker,
            ticker_data=ticker_data,
            df_15m=df_15m,
            df_4h=df_4h,
            df_d=df_d,
            volumen_promedio=volumen_promedio,
            atr_pct=atr_pct,
            ivr=ivr,
            sobre_sma200=signals.get("sobre_sma200"),
            sobre_ema50=signals.get("sobre_ema50"),
            cruce_ema_921_15m=signals.get("cruce_ema_921_15m"),
            cruce_ema_921_4h=signals.get("cruce_ema_921_4h"),
            cruce_ema_921_d=signals.get("cruce_ema_921_d"),
            cruce_ema_921_5m=signals.get("cruce_ema_921_5m"),
            warning=warning,
            ultimo_precio=ticker_data.precio,
            volumen_acumulado=float(ticker_data.volumen_actual or 0),
            max_dia=ticker_data.precio,
            min_dia=ticker_data.precio,
            suscrito_en=datetime.utcnow(),
        )
        cache.velas_hoy = _df_a_velas(df_5m)
        cache.relvol_categoria = _categoria_relvol(self._relvol_actual(cache), self._config)
        self._tickers[ticker] = cache

    def actualizar_tick(
        self,
        ticker: str,
        precio: float,
        bid: Optional[float],
        ask: Optional[float],
        volumen_total: float,
        timestamp: datetime,
    ) -> bool:
        cache = self._tickers.get(ticker)
        if cache is None or precio <= 0:
            return False

        delta_vol = max(0.0, volumen_total - cache.volumen_acumulado)
        cache._cum_pv += precio * delta_vol
        cache._cum_v += delta_vol
        if cache._cum_v > 0:
            cache.vwap = cache._cum_pv / cache._cum_v

        cache.ultimo_precio = precio
        cache.bid = bid
        cache.ask = ask
        cache.volumen_acumulado = volumen_total

        evento = False

        if cache.vwap is not None:
            sobre_vwap_actual = precio > cache.vwap
            if cache.sobre_vwap is not None and sobre_vwap_actual != cache.sobre_vwap:
                evento = True
            cache.sobre_vwap = sobre_vwap_actual

        if cache.max_dia is None or precio > cache.max_dia:
            cache.max_dia = precio
            evento = True
        if cache.min_dia is None or precio < cache.min_dia:
            cache.min_dia = precio
            evento = True

        categoria_actual = _categoria_relvol(self._relvol_actual(cache), self._config)
        if cache.relvol_categoria is not None and categoria_actual != cache.relvol_categoria:
            evento = True
        cache.relvol_categoria = categoria_actual

        return evento

    def actualizar_vela_1m(self, ticker: str, vela_1m: Vela) -> bool:
        cache = self._tickers.get(ticker)
        if cache is None:
            return False

        bucket_ts = _floor_5min(vela_1m.timestamp)
        ultima = cache.velas_hoy[-1] if cache.velas_hoy else None

        if ultima is not None and ultima.timestamp == bucket_ts:
            ultima.high = max(ultima.high, vela_1m.high)
            ultima.low = min(ultima.low, vela_1m.low)
            ultima.close = vela_1m.close
            ultima.volume += vela_1m.volume
            return False  # sigue dentro de la misma ventana de 5m — no cerró

        vela_cerro = ultima is not None
        cache.velas_hoy.append(Vela(
            timestamp=bucket_ts,
            open=vela_1m.open,
            high=vela_1m.high,
            low=vela_1m.low,
            close=vela_1m.close,
            volume=vela_1m.volume,
        ))

        if not vela_cerro:
            return False  # primerísima vela del día, nada contra qué comparar

        df_5m = _velas_a_df(cache.velas_hoy)
        cruce_actual = detect_cruce_ema(df_5m, self._config.ema_rapida, self._config.ema_media)
        cruce_previo = cache.cruce_ema_921_5m
        evento = (
            cruce_previo is not None
            and cruce_actual is not None
            and cruce_actual != cruce_previo
        )
        cache.cruce_ema_921_5m = cruce_actual
        return evento

    def snapshot(self, ticker: str) -> Optional[DatosTickerCompletos]:
        cache = self._tickers.get(ticker)
        if cache is None:
            return None
        td = cache.ticker_data
        warning = cache.warning
        return DatosTickerCompletos(
            ticker=ticker,
            fecha=date.today(),
            timestamp=datetime.utcnow(),
            fuente=FuenteDatos.LIVE,
            precio=cache.ultimo_precio,
            variacion_diaria_pct=td.variacion_diaria_pct if td else 0.0,
            relvol=self._relvol_actual(cache),
            atr_pct=cache.atr_pct,
            volumen_actual=int(cache.volumen_acumulado),
            sobre_sma200=cache.sobre_sma200,
            sobre_ema50=cache.sobre_ema50,
            cruce_ema_921_5m=cache.cruce_ema_921_5m,
            cruce_ema_921_15m=cache.cruce_ema_921_15m,
            cruce_ema_921_4h=cache.cruce_ema_921_4h,
            cruce_ema_921_d=cache.cruce_ema_921_d,
            ivr=cache.ivr,
            warning_calendar=warning.nivel if warning and warning.disponible else None,
            earnings_24h=warning.earnings_24h if warning else False,
            evento_macro_24h=warning.evento_macro_24h if warning else False,
            filing_8k_24h=warning.filing_8k_24h if warning else False,
            upgrade_downgrade_24h=warning.upgrade_downgrade_24h if warning else False,
            catalizador_detectado=warning.catalizador_detectado if warning else False,
            volumen_promedio=cache.volumen_promedio,
            bid=cache.bid,
            ask=cache.ask,
        )
