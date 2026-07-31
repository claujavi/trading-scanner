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
from datetime import datetime
from enum import Enum
from typing import Optional


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
    _grupo: list[VelaPattern] = field(default_factory=list)
    _barras_en_estado2: int = 0

    def _registrar_rango_previo(self, vela: VelaPattern) -> None:
        self._rangos_previos.append(vela.high - vela.low)
        if len(self._rangos_previos) > self.ventana_inicio_barras:
            self._rangos_previos.pop(0)

    def _reset(self) -> None:
        self.estado = Estado3BP.SIN_PATRON
        self._barra1 = None
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
                evento = EventoPatron3BP(
                    estado=Estado3BP.ENTRADA,
                    timestamp=vela.timestamp,
                    tipo=tipo,
                    entry=entry,
                    stop=stop,
                    tier=tier,
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
