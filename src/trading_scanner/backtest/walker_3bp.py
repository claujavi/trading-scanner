"""
walker_3bp.py — backtest del módulo 3BP/4BP (paso 4 de
docs/spec_modulo_3bp_4bp.md, "Orden de trabajo acordado"). Reusa el mismo
Detector3BP que corre en vivo (fetchers/market_data_cache.py) — un
caminador vela por vela, no el patrón "un día = un contexto" de
backtest/runner.py (incompatible con una máquina de estados intradía, ver
checkpoint del paso 4, ya resuelto).

Reseteo diario como el vivo (market_data_cache.py::seed()/
_crear_detector_3bp): un Detector3BP nuevo y un contexto de velas vacío por
cada día de trading — nunca hereda contexto de días previos. ATR14 y volumen
promedio de referencia se calculan sobre la propia serie del día (no el
ATR%/volumen diario que usa el clasificador de 6 criterios), de forma
incremental (_ContextoIncremental, verificado igual a
market_data_cache._atr14_de_velas/_volumen_promedio_de_velas que usa el
stream) para que un trial del optimizador no recalcule todo por cada barra.

Horario (ScanConfig.bp34_entradas_solo_sesion_regular / _ventana_entrada_
minutos): las velas de Schwab traen madrugada y pre-market, y el 60% de las
entradas del backtest original eran de ahí (no operables). Con el filtro
activo el detector se alimenta desde las 4:00 NY —el contexto de pre-market
es parte del patrón, la "barra ancha" suele ser la de las 9:30 contra un ATR
de pre-market chico— pero solo se aceptan ENTRADAS dentro de la sesión
regular (y de la ventana, si se pide).

Una entrada (Estado 3) se sigue con el precio real post-señal DENTRO del
mismo día (3BP es una señal de timing intradía — la spec no define
sostenimiento multi-día para este módulo, a diferencia del SWING del
clasificador de 6 criterios) hasta tocar target, tocar stop, o el cierre
forzado a las 15:55 NY (misma regla que simulator.py, reusada — no
reimplementada).
"""

from datetime import date, datetime
from typing import Optional

import polars as pl

from ..engine.pattern_3bp import (
    _APERTURA_NY_MIN,
    _CIERRE_NY_MIN,
    Estado3BP,
    minutos_desde_apertura_ny,
)
from ..fetchers import history_cache
from ..fetchers.market_data_cache import Vela, _a_vela_pattern, _crear_detector_3bp
from ..logging_setup import console
from ..models import Bp34Evento, FuenteDatos, ResultadoBp34, ScanConfig
from .runner import _dias_habiles
from .simulator import _truncar_a_cierre_forzado

_MINUTOS_POR_TIMEFRAME = {"5m": 5, "15m": 15}

_INICIO_CONTEXTO_NY_MIN = 4 * 60  # 4:00: inicio del pre-market, desde acá se alimenta el detector

_ATR_ALPHA = 1.0 / 14  # mismo período fijo que market_data_cache._atr14_de_velas


def _minutos_ny_expr() -> pl.Expr:
    """Minutos desde medianoche NY de cada vela. Los timestamps de Schwab
    son naive pero representan un instante UTC (ver
    simulator.py::_truncar_a_cierre_forzado) — hay que declararlos UTC y
    convertir, nunca leer la hora tal cual."""
    ts = pl.col("timestamp").dt.replace_time_zone("UTC").dt.convert_time_zone("America/New_York")
    return ts.dt.hour().cast(pl.Int32) * 60 + ts.dt.minute().cast(pl.Int32)


def evento_en_ventana_permitida(ts: datetime, config: ScanConfig) -> bool:
    """True si `config.bp34_entradas_solo_sesion_regular` está desactivado
    (sin restricción), o si `ts` cae dentro de la sesión regular (9:30-16:00
    NY) y, si se configuró `bp34_ventana_entrada_minutos` > 0, dentro de esa
    ventana desde la apertura. Comparte semántica exacta con el filtro que
    aplica el walker de backtest (`_caminar_dia`/`entradas_desde`/
    `entradas_hasta`) — usada también por el wireo en vivo (`main.py::
    _on_evento_3bp`) para que lo que se persiste en vivo sea comparable a lo
    calibrado, en vez de aceptar entradas a cualquier hora."""
    if not config.bp34_entradas_solo_sesion_regular:
        return True
    minutos = minutos_desde_apertura_ny(ts)
    if minutos < 0 or minutos >= (_CIERRE_NY_MIN - _APERTURA_NY_MIN):
        return False
    if config.bp34_ventana_entrada_minutos > 0 and minutos >= config.bp34_ventana_entrada_minutos:
        return False
    return True


def _filtrar_contexto_y_sesion(df: pl.DataFrame) -> pl.DataFrame:
    """Velas 4:00 <= hora < 16:00 NY: pre-market (contexto para el detector)
    más sesión regular. Descarta la madrugada (00:00-4:00) y el after-hours,
    que Schwab incluye en las velas intradía y donde nadie opera."""
    if df.is_empty():
        return df
    minutos = _minutos_ny_expr()
    return df.filter((minutos >= _INICIO_CONTEXTO_NY_MIN) & (minutos < _CIERRE_NY_MIN))


class _ContextoIncremental:
    """ATR14 y volumen promedio "hasta esta barra" en O(1) por barra.

    Reemplaza llamar a market_data_cache._atr14_de_velas(contexto) /
    _volumen_promedio_de_velas(contexto) con `contexto = velas[: i + 1]` en
    cada barra: esas reconvierten toda la lista a DataFrame y recalculan
    desde cero (~1 ms por llamada, cuadratico por dia) y eran el 95% del
    tiempo de un trial del optimizador. Da EXACTAMENTE los mismos valores
    (tests/unit/test_walker_3bp.py compara contra ambas funciones sobre datos
    aleatorios): calc_atr es TR + EWM(alpha=1/14, adjust=False), con
    TR(primera barra) = high - low; el volumen promedio es la media de las
    barras ANTERIORES a la actual, y hacen falta al menos 2 (para ATR14) /
    2 anteriores (para el volumen), igual que las funciones originales."""

    def __init__(self) -> None:
        self._n = 0
        self._atr: Optional[float] = None
        self._prev_close: Optional[float] = None
        self._vol_anteriores = 0.0

    def avanzar(self, vela: Vela) -> tuple[Optional[float], Optional[float]]:
        """Incorpora `vela` y devuelve (atr14, volumen_promedio_de_las_anteriores)."""
        rango = vela.high - vela.low
        if self._prev_close is None:
            tr = rango
        else:
            tr = max(rango, abs(vela.high - self._prev_close), abs(vela.low - self._prev_close))
        self._atr = tr if self._atr is None else self._atr + _ATR_ALPHA * (tr - self._atr)

        anteriores = self._n
        vol_promedio = (self._vol_anteriores / anteriores) if anteriores >= 2 else None
        self._n += 1
        self._vol_anteriores += vela.volume
        self._prev_close = vela.close

        atr14 = self._atr if self._n >= 2 else None
        return atr14, vol_promedio


def _df_a_velas(df: pl.DataFrame) -> list[Vela]:
    if df.is_empty():
        return []
    return [
        Vela(
            timestamp=row["timestamp"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )
        for row in df.sort("timestamp").iter_rows(named=True)
    ]


def _resolver_entrada(
    velas_desde_gatillo: list[Vela],
    entry: float,
    stop: float,
    target_r: float,
    timeframe: str,
    slippage_bps: float = 0.0,
) -> tuple[ResultadoBp34, float, float, float, int]:
    """`velas_desde_gatillo` incluye la barra gatillo (índice 0, la que
    disparó ENTRADA) y todo lo que sigue en el día, ya truncado al cierre
    forzado. La barra gatillo se revisa también por target/stop — el
    breakout que dispara la entrada puede, en esa misma barra, seguir
    moviéndose hasta el target o revertir hasta el stop, y con solo OHLC
    no hay forma de saber el orden real intra-barra. Mismo criterio
    pesimista que simulator.py::_fixed_rr: si una barra toca ambos, gana
    el stop. Devuelve (resultado, resultado_r, mfe_r, mae_r,
    tiempo_en_trade_minutos).

    `slippage_bps` (por lado, misma convención que simulator.py::_slippage):
    la entrada se llena `slippage_bps` más cara y cada salida (stop, target
    o cierre) `slippage_bps` más barata. El R sigue medido contra el riesgo
    teórico (entry - stop), así que un stop pierde -1R - costo, no -1R
    exacto — el costo en R crece cuanto más corto es el stop (10 bps de
    ida y vuelta se comen 0.5R con un stop de 0.2% del precio y 0.05R con
    uno de 2%). mfe_r/mae_r quedan sin slippage: son informativos del
    movimiento del precio, no de un fill. Con slippage_bps=0 el resultado
    es idéntico al de antes (fills perfectos)."""
    stop_dist = entry - stop
    if not velas_desde_gatillo or stop_dist <= 0:
        return ResultadoBp34.SIN_DEFINIR, 0.0, 0.0, 0.0, 0

    target = entry + stop_dist * target_r
    minutos_vela = _MINUTOS_POR_TIMEFRAME[timeframe]
    slip = slippage_bps / 10_000

    def _costo_r(salida: float) -> float:
        return slip * (salida + entry) / stop_dist

    mfe_r = 0.0
    mae_r = 0.0
    for i, vela in enumerate(velas_desde_gatillo):
        mfe_r = max(mfe_r, (vela.high - entry) / stop_dist)
        mae_r = min(mae_r, (vela.low - entry) / stop_dist)
        if vela.low <= stop:
            return ResultadoBp34.STOP, -1.0 - _costo_r(stop), mfe_r, mae_r, i * minutos_vela
        if vela.high >= target:
            return ResultadoBp34.TARGET, target_r - _costo_r(target), mfe_r, mae_r, i * minutos_vela

    cierre = velas_desde_gatillo[-1].close
    resultado_r = (cierre - entry) / stop_dist - _costo_r(cierre)
    tiempo = (len(velas_desde_gatillo) - 1) * minutos_vela
    return ResultadoBp34.SIN_DEFINIR, resultado_r, mfe_r, mae_r, tiempo


def _caminar_dia(
    velas_dia: list[Vela],
    ticker: str,
    timeframe: str,
    fecha: date,
    config: ScanConfig,
    fuente: FuenteDatos,
    entradas_desde: int = 0,
    entradas_hasta: Optional[int] = None,
) -> list[Bp34Evento]:
    """Camina un día de un ticker+timeframe: detector fresco, contexto
    vacío — mismo reseteo diario que ya hace seed() en vivo. Un mismo día
    puede producir varias entradas independientes (el detector vuelve a
    SIN_PATRON apenas emite ENTRADA, ver pattern_3bp.py::procesar_barra).

    `entradas_desde` / `entradas_hasta` (índices sobre `velas_dia`,
    [desde, hasta)): solo las barras de ese rango pueden originar una
    ENTRADA (ver ScanConfig.bp34_entradas_solo_sesion_regular / _ventana_
    entrada_minutos). El detector se alimenta igual con TODAS las barras
    previas —el contexto de pre-market es parte del patrón— y una entrada
    aceptada se resuelve con TODAS las barras restantes del día, no se corta
    en `entradas_hasta`. Una ENTRADA anterior a `entradas_desde` reinicia al
    detector pero no se registra. Sin límites (defaults) = todo el día."""
    detector = _crear_detector_3bp(config, timeframe)
    target_r = getattr(config, f"bp34_target_r_{timeframe}")
    config_snapshot = config.model_dump(mode="json")
    limite = len(velas_dia) if entradas_hasta is None else entradas_hasta
    contexto = _ContextoIncremental()

    eventos: list[Bp34Evento] = []
    for i, vela in enumerate(velas_dia):
        if i >= limite:
            break
        atr14, volumen_promedio = contexto.avanzar(vela)
        if atr14 is None:
            continue  # todavía no hay suficiente contexto de sesión — mismo criterio que en vivo

        evento = detector.procesar_barra(_a_vela_pattern(vela), atr14, volumen_promedio)
        if evento is None or evento.estado != Estado3BP.ENTRADA:
            continue
        if i < entradas_desde:
            continue  # entrada fuera de horario (pre-market): no operable, no se registra

        # Stop demasiado corto para operarse (ver ScanConfig.bp34_stop_min_pct):
        # se descarta la entrada, no se cuenta como pérdida ni ganancia.
        if (evento.entry - evento.stop) / evento.entry * 100 < config.bp34_stop_min_pct:
            continue
        if config.bp34_solo_tier_confirmado and evento.tier != "confirmado":
            continue  # ver ScanConfig.bp34_solo_tier_confirmado

        resultado, resultado_r, mfe_r, mae_r, tiempo = _resolver_entrada(
            velas_dia[i:], evento.entry, evento.stop, target_r, timeframe, config.slippage_bps
        )
        eventos.append(Bp34Evento(
            ticker=ticker,
            timeframe=timeframe,
            fecha=fecha,
            timestamp=vela.timestamp,
            fuente=fuente,
            tipo=evento.tipo,
            tier=evento.tier,
            entry=evento.entry,
            stop=evento.stop,
            target=evento.entry + (evento.entry - evento.stop) * target_r,
            resultado=resultado,
            resultado_r=resultado_r,
            mfe_r=mfe_r,
            mae_r=mae_r,
            tiempo_en_trade_minutos=tiempo,
            barra1_wrb_ratio=evento.barra1_wrb_ratio,
            config_snapshot=config_snapshot,
        ))
    return eventos


async def caminar_3bp(
    ticker: str, timeframe: str, fecha_inicio: date, fecha_fin: date, config: ScanConfig
) -> list[Bp34Evento]:
    """Backtest del módulo 3BP/4BP para un ticker+timeframe — un
    Detector3BP fresco por día, reusando el mismo motor que corre en vivo.
    `timeframe`: "5m" | "15m" — perfiles independientes, nunca mezclados
    (spec, sección 1)."""
    piso_intraday = history_cache.FECHA_INICIO_DEFAULT[timeframe]
    if fecha_fin < piso_intraday:
        return []  # Schwab no tiene intradía tan atrás, ver CLAUDE.md
    fecha_inicio_efectiva = max(fecha_inicio, piso_intraday)

    try:
        df_full = await history_cache.get_history(ticker, timeframe, fecha_inicio_efectiva, fecha_fin)
    except Exception as exc:
        console.log(f"[yellow]Walker 3BP: sin historial de {ticker} ({timeframe}): {exc}[/yellow]")
        return []

    if df_full.is_empty():
        return []

    solo_sesion = config.bp34_entradas_solo_sesion_regular
    if solo_sesion:
        # Una sola vez por ticker (no por día): también achica el df que
        # recorre filter_range() en cada día del loop.
        df_full = _filtrar_contexto_y_sesion(df_full)
        if df_full.is_empty():
            return []

    eventos: list[Bp34Evento] = []
    for dia in _dias_habiles(fecha_inicio_efectiva, fecha_fin):
        df_dia = history_cache.filter_range(df_full, dia, dia)
        df_dia = _truncar_a_cierre_forzado(df_dia)
        if df_dia.is_empty():
            continue

        entradas_desde, entradas_hasta = 0, None
        if solo_sesion:
            minutos = _minutos_ny_expr()
            df_dia = df_dia.sort("timestamp")  # los índices de abajo son posiciones en orden cronológico
            entradas_desde = df_dia.filter(minutos < _APERTURA_NY_MIN).height
            if config.bp34_ventana_entrada_minutos > 0:
                entradas_hasta = df_dia.filter(
                    minutos < _APERTURA_NY_MIN + config.bp34_ventana_entrada_minutos
                ).height

        velas_dia = _df_a_velas(df_dia)
        eventos.extend(_caminar_dia(
            velas_dia, ticker, timeframe, dia, config, FuenteDatos.HISTORICO,
            entradas_desde=entradas_desde, entradas_hasta=entradas_hasta,
        ))
    return eventos
