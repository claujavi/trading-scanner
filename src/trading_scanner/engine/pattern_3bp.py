"""Módulo de detección 3BP/4BP (Bar Play) — señal de timing paralela al
clasificador de 6 criterios, ver docs/spec_modulo_3bp_4bp.md.

Función pura / máquina de estados en memoria: no toca red, Schwab ni el
stream — instanciar un `Detector3BP` por (ticker, timeframe) y llamar
`procesar_barra()` con cada vela ya cerrada, en orden cronológico. No se
mezcla con el score de 6 criterios ni con la clasificación DAY/SWING.

Solo direcciones alcistas (+3BP/+4BP) en esta fase — ver "Fuera de
alcance" en la spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from ..models import ResultadoBp34


# "3 y 4 Bar Play" es una definición cerrada, no "N Bar Play" — el grupo
# de consolidación (barra 2, y barra 3 para 4BP) tiene tope duro de 2
# barras. Una candidata a 3ra barra de grupo no extiende el patrón, lo
# descarta (ver Detector3BP.procesar_barra).
_GRUPO_MAX_BARRAS = 2


class Estado3BP(str, Enum):
    SIN_PATRON = "SIN_PATRON"
    POSIBLE = "POSIBLE"                      # barra 1 (WRB) detectada
    ESPERANDO_ENTRADA = "ESPERANDO_ENTRADA"  # grupo (barra 2, y 3 si aplica) confirmado
    ENTRADA = "ENTRADA"                      # barra gatillo rompió el máximo del grupo


@dataclass(frozen=True)
class VelaPattern:
    timestamp: datetime
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class EventoPatron3BP:
    """Contrato de salida del módulo — ver spec, sección 4. `ticker` y
    `timeframe` no viven acá (son contexto del caller, que instancia un
    Detector3BP por combinación); se agregan en la capa de wireo."""
    estado: Estado3BP
    timestamp: datetime
    tipo: Optional[str] = None       # "3BP" | "4BP" — solo definido en ENTRADA
    entry: Optional[float] = None    # solo en ENTRADA
    stop: Optional[float] = None     # solo en ENTRADA
    tier: Optional[str] = None       # "confirmado" | "sin_confirmar" — solo en ENTRADA
    barra1_wrb_ratio: Optional[float] = None
    # (high-low de la barra 1) / ATR14 al momento en que se detectó como WRB
    # — solo en ENTRADA. Por construcción siempre >= wrb_multiplicador (esa
    # es la condición que la calificó como barra 1, ver _es_wrb_que_inicia),
    # así que cuantifica CUÁNTO se pasó del umbral, no si lo pasó. Informativo
    # para análisis de calidad de señal (ver docs/backlog_mejoras_clasificador.md
    # y correlacion_3bp_calidad.py) — no participa de ninguna decisión del
    # propio detector.


@dataclass
class Detector3BP:
    """Máquina de estados de la spec, sección 3. Una instancia por
    (ticker, timeframe) — mantiene estado propio, se llama una vez por
    vela nueva ya cerrada. ATR14 y volumen promedio son contexto externo
    (el caller ya los calcula del lado del pipeline/stream) — se pasan en
    cada llamada a `procesar_barra`, el detector no los calcula."""

    wrb_multiplicador: float
    tolerancia_pct: float
    n_invalidacion: int
    ventana_inicio_barras: int
    volumen_confirmado_mult: float

    estado: Estado3BP = Estado3BP.SIN_PATRON
    _rangos_previos: list[float] = field(default_factory=list)
    _barra1: Optional[VelaPattern] = None
    _barra1_atr14: Optional[float] = None
    _grupo: list[VelaPattern] = field(default_factory=list)
    _barras_en_estado2: int = 0

    def _registrar_rango_previo(self, vela: VelaPattern) -> None:
        self._rangos_previos.append(vela.high - vela.low)
        if len(self._rangos_previos) > self.ventana_inicio_barras:
            self._rangos_previos.pop(0)

    def _reset(self) -> None:
        self.estado = Estado3BP.SIN_PATRON
        self._barra1 = None
        self._barra1_atr14 = None
        self._grupo = []
        self._barras_en_estado2 = 0

    def _es_wrb_que_inicia(self, vela: VelaPattern, atr14: float) -> bool:
        rango = vela.high - vela.low
        umbral = self.wrb_multiplicador * atr14
        if rango < umbral:
            return False
        # Ninguna de las `ventana_inicio_barras` barras previas debe tener
        # ese rango — evita marcar como barra 1 una vela grande en medio
        # de una tendencia ya extendida.
        return all(r < umbral for r in self._rangos_previos)

    def _nivel_gatillo(self) -> float:
        """Máximo del grupo (barra 1 + barras de consolidación ya
        confirmadas) — el nivel que una barra gatillo tiene que romper."""
        maximos = [self._barra1.high] + [b.high for b in self._grupo]
        return max(maximos)

    def _tolerancia_absoluta(self) -> float:
        rango_barra1 = self._barra1.high - self._barra1.low
        return self.tolerancia_pct * rango_barra1

    def _punto_medio_barra1(self) -> float:
        return self._barra1.low + 0.5 * (self._barra1.high - self._barra1.low)

    def _bar_confirma_grupo(self, vela: VelaPattern) -> bool:
        """Condición de posición + techo (spec sección 2): mínimo >= punto
        medio de la barra 1, máximo <= techo de la barra 1 con tolerancia
        (esto acota indirectamente que los máximos del grupo sean
        "relativamente iguales" entre sí, ya que todos quedan atados al
        mismo techo de referencia)."""
        pm = self._punto_medio_barra1()
        techo = self._barra1.high + self._tolerancia_absoluta()
        return vela.low >= pm and vela.high <= techo

    def _invalida_por_estructura(self, vela: VelaPattern) -> bool:
        return vela.close < self._barra1.low

    def procesar_barra(
        self,
        vela: VelaPattern,
        atr14: float,
        volumen_promedio: Optional[float] = None,
    ) -> Optional[EventoPatron3BP]:
        """Procesa una vela nueva ya cerrada. Devuelve un evento si hubo
        transición de estado (POSIBLE, ESPERANDO_ENTRADA, ENTRADA, o vuelta
        a SIN_PATRON por invalidación) — None si la vela no cambió nada
        (ej. una barra más de consolidación dentro de la tolerancia sin
        romper ni invalidar). `volumen_promedio` solo hace falta si se
        llega a evaluar una barra gatillo — sin él, el tier de esa
        entrada queda "sin_confirmar" por defecto (no bloquea la señal,
        ver spec: confirmación de volumen es opcional, no bloqueante)."""
        evento: Optional[EventoPatron3BP] = None

        if self.estado == Estado3BP.SIN_PATRON:
            if atr14 and atr14 > 0 and self._es_wrb_que_inicia(vela, atr14):
                self.estado = Estado3BP.POSIBLE
                self._barra1 = vela
                self._barra1_atr14 = atr14
                self._grupo = []
                evento = EventoPatron3BP(estado=Estado3BP.POSIBLE, timestamp=vela.timestamp)

        elif self.estado == Estado3BP.POSIBLE:
            if self._invalida_por_estructura(vela):
                self._reset()
                evento = EventoPatron3BP(estado=Estado3BP.SIN_PATRON, timestamp=vela.timestamp)
            elif self._bar_confirma_grupo(vela):
                self._grupo.append(vela)
                self.estado = Estado3BP.ESPERANDO_ENTRADA
                self._barras_en_estado2 = 0
                evento = EventoPatron3BP(estado=Estado3BP.ESPERANDO_ENTRADA, timestamp=vela.timestamp)
            else:
                # Ni invalida ni confirma grupo (ej. rompe por arriba sin
                # haber ninguna barra de consolidación todavía) — falta la
                # estructura mínima (bar1 + al menos 1 barra de grupo), se
                # descarta sin señal.
                self._reset()

        elif self.estado == Estado3BP.ESPERANDO_ENTRADA:
            self._barras_en_estado2 += 1
            if self._invalida_por_estructura(vela):
                self._reset()
                evento = EventoPatron3BP(estado=Estado3BP.SIN_PATRON, timestamp=vela.timestamp)
            elif vela.high > self._nivel_gatillo():
                # Con el tope de _GRUPO_MAX_BARRAS, "else" acá solo puede
                # significar len(grupo) == 2 — sin ambigüedad con grupos
                # más largos (ver tope aplicado más abajo).
                tipo = "3BP" if len(self._grupo) == 1 else "4BP"
                entry = self._nivel_gatillo()
                stop = min([self._barra1.low] + [b.low for b in self._grupo])
                tier = "sin_confirmar"
                if volumen_promedio and volumen_promedio > 0:
                    if vela.volume >= self.volumen_confirmado_mult * volumen_promedio:
                        tier = "confirmado"
                barra1_wrb_ratio = None
                if self._barra1_atr14:
                    barra1_wrb_ratio = (self._barra1.high - self._barra1.low) / self._barra1_atr14
                evento = EventoPatron3BP(
                    estado=Estado3BP.ENTRADA,
                    timestamp=vela.timestamp,
                    tipo=tipo,
                    entry=entry,
                    stop=stop,
                    tier=tier,
                    barra1_wrb_ratio=barra1_wrb_ratio,
                )
                self._reset()
            elif self._bar_confirma_grupo(vela):
                if len(self._grupo) < _GRUPO_MAX_BARRAS:
                    self._grupo.append(vela)
                    # Sigue en ESPERANDO_ENTRADA — no se emite evento por
                    # cada barra de consolidación adicional, solo en
                    # transiciones.
                else:
                    # El grupo ya está en el tope (barra 2 + barra 3). Esta
                    # barra calificaría para extenderlo a una 3ra, pero eso
                    # ya no es un 3BP/4BP válido (definición cerrada, no
                    # "N Bar Play") — descarta el patrón entero en vez de
                    # etiquetarlo genéricamente como 4BP.
                    self._reset()
                    evento = EventoPatron3BP(estado=Estado3BP.SIN_PATRON, timestamp=vela.timestamp)
            elif self._barras_en_estado2 >= self.n_invalidacion:
                self._reset()
                evento = EventoPatron3BP(estado=Estado3BP.SIN_PATRON, timestamp=vela.timestamp)
            # Barra que no confirma grupo, no invalida y no dispara: no
            # suma al grupo, pero sí cuenta para el N de invalidación
            # (ya incrementado arriba).

        self._registrar_rango_previo(vela)
        return evento


# ── Horario NY — compartido por el filtro de sesión (backtest/walker_3bp.py)
# y por el seguimiento en vivo de acá abajo, para que ambos usen exactamente
# la misma conversión (mismo criterio "naive pero UTC" de todo el sistema).

_NY_TZ = ZoneInfo("America/New_York")
_APERTURA_NY_MIN = 9 * 60 + 30   # 9:30
_CIERRE_NY_MIN = 16 * 60         # 16:00 (exclusivo)
# 15:55 NY en minutos desde la apertura — mismo cierre forzado que
# backtest/simulator.py::_CIERRE_FORZADO_HORA_NY, expresado en esta unidad.
_MINUTOS_CIERRE_FORZADO = 15 * 60 + 55 - _APERTURA_NY_MIN
_MINUTOS_POR_TIMEFRAME = {"5m": 5, "15m": 15}


def minutos_desde_apertura_ny(ts: datetime) -> int:
    """Minutos desde las 9:30 NY del timestamp dado (naive pero UTC, mismo
    contrato que el resto del sistema) — negativo si es antes de la
    apertura. Usado por el filtro de sesión del walker de backtest y por
    `SeguidorPosicion3BP` de acá abajo."""
    ts_ny = ts.replace(tzinfo=timezone.utc).astimezone(_NY_TZ)
    return ts_ny.hour * 60 + ts_ny.minute - _APERTURA_NY_MIN


def fecha_ny(ts: datetime) -> date:
    """Fecha de trading NY del timestamp dado (naive pero UTC). Usada por
    `SeguidorPosicion3BP` acá abajo y por `main.py::_on_evento_3bp` para
    fechar el evento por la sesión NY real, no por la fecha local del
    servidor (que puede diferir cerca de la medianoche, aunque en la
    práctica el filtro de sesión regular ya acota las entradas a un rango
    horario bien dentro del mismo día calendario en cualquier huso horario
    razonable)."""
    return ts.replace(tzinfo=timezone.utc).astimezone(_NY_TZ).date()


class SeguidorPosicion3BP:
    """Sigue en vivo una entrada 3BP/4BP ya aceptada, vela a vela, hasta que
    toca target, toca stop, o llega el cierre forzado (15:55 NY) — la
    versión "streaming" de `backtest/walker_3bp.py::_resolver_entrada`, que
    recibe de una sola vez todas las velas futuras del día porque en
    backtest ya están todas disponibles de antemano. Acá se alimenta una
    vela genuina por vez a medida que cierra (`procesar_vela()`), tanto
    para el seguimiento realmente en vivo (una vela nueva del stream) como
    para "ponerse al día" tras un reinicio del servidor, alimentando de una
    sola vez el historial real ya transcurrido (ver `main.py`, reconciliación
    al reconectar el stream) — mismo objeto, mismo método, ambos casos.

    Misma semántica exacta que `_resolver_entrada`: prioridad al stop si una
    vela toca ambos niveles, mismo costo de `slippage_bps` en la salida (la
    entrada ya se asume pagada). 3BP nunca sostiene una posición de un día
    para el otro (a diferencia del SWING del clasificador de 6 criterios):
    cualquier vela de un día distinto al de la entrada, o posterior al
    cierre forzado, dispara la resolución usando el cierre de la última
    vela válida vista — nunca deja una posición "colgada" indefinidamente."""

    def __init__(
        self, ticker: str, timeframe: str, fecha: date, entry: float, stop: float,
        target: float, slippage_bps: float = 0.0,
    ):
        self.ticker = ticker
        self.timeframe = timeframe
        self.fecha = fecha
        self.entry = entry
        self.stop = stop
        self.target = target
        self.slippage_bps = slippage_bps
        self.resuelto = False
        self._mfe_r = 0.0
        self._mae_r = 0.0
        self._velas_vistas = 0
        self._ultima_vela = None

    def procesar_vela(self, vela) -> Optional[tuple[ResultadoBp34, float, float, float, int]]:
        """`vela`: cualquier objeto con `.timestamp`/`.high`/`.low`/`.close`
        (duck-typing — sirve tanto `Vela` como `VelaPattern`). Devuelve
        `(resultado, resultado_r, mfe_r, mae_r, tiempo_en_trade_minutos)` si
        esta vela resolvió la posición — `None` si sigue abierta. No hace
        nada si ya estaba resuelta (llamar de más es inofensivo)."""
        if self.resuelto:
            return None
        stop_dist = self.entry - self.stop
        if stop_dist <= 0:
            self.resuelto = True
            return ResultadoBp34.SIN_DEFINIR, 0.0, 0.0, 0.0, 0

        minutos_vela = _MINUTOS_POR_TIMEFRAME[self.timeframe]
        slip = self.slippage_bps / 10_000

        def _costo_r(salida: float) -> float:
            return slip * (salida + self.entry) / stop_dist

        # vela de otro día, o posterior al cierre forzado del día de la
        # entrada — no se procesa (el backtest tampoco la incluiría),
        # se cierra con el cierre de la última vela válida ya vista.
        if fecha_ny(vela.timestamp) != self.fecha or minutos_desde_apertura_ny(vela.timestamp) > _MINUTOS_CIERRE_FORZADO:
            return self._cerrar_forzado(stop_dist, minutos_vela, _costo_r)

        self._velas_vistas += 1
        self._ultima_vela = vela
        self._mfe_r = max(self._mfe_r, (vela.high - self.entry) / stop_dist)
        self._mae_r = min(self._mae_r, (vela.low - self.entry) / stop_dist)

        if vela.low <= self.stop:
            self.resuelto = True
            tiempo = (self._velas_vistas - 1) * minutos_vela
            return ResultadoBp34.STOP, -1.0 - _costo_r(self.stop), self._mfe_r, self._mae_r, tiempo
        if vela.high >= self.target:
            self.resuelto = True
            target_r = (self.target - self.entry) / stop_dist
            tiempo = (self._velas_vistas - 1) * minutos_vela
            return ResultadoBp34.TARGET, target_r - _costo_r(self.target), self._mfe_r, self._mae_r, tiempo

        if minutos_desde_apertura_ny(vela.timestamp) + minutos_vela > _MINUTOS_CIERRE_FORZADO:
            # esta vela es la última del día permitida (la siguiente ya
            # caería después de las 15:55) — mismo criterio que el último
            # elemento de `velas_desde_gatillo` en _resolver_entrada.
            return self._cerrar_forzado(stop_dist, minutos_vela, _costo_r)
        return None

    def _cerrar_forzado(self, stop_dist: float, minutos_vela: int, _costo_r) -> tuple[ResultadoBp34, float, float, float, int]:
        self.resuelto = True
        if self._ultima_vela is None:
            # nunca llegó a ver ninguna vela válida (ej. reconciliación sin
            # historial disponible ese día) — sin dato real para resolver.
            return ResultadoBp34.SIN_DEFINIR, 0.0, self._mfe_r, self._mae_r, 0
        cierre = self._ultima_vela.close
        resultado_r = (cierre - self.entry) / stop_dist - _costo_r(cierre)
        tiempo = (self._velas_vistas - 1) * minutos_vela
        return ResultadoBp34.SIN_DEFINIR, resultado_r, self._mfe_r, self._mae_r, tiempo
