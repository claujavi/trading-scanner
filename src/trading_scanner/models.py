"""
Modelos de datos Pydantic.

Todos los modelos son Pydantic v2 BaseModel.
Config snapshot siempre se guarda completo para reproducibilidad.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# ENUMS
# ============================================================================


class ModoSalida(str, Enum):
    """Modos de gestión de posición."""

    FIXED_RR = "FIXED_RR"  # salir en target fijo (rr_target)
    TRAILING_EOD = "TRAILING_EOD"  # trailing stop hasta fin de sesión
    PARTIAL_SCALE = "PARTIAL_SCALE"  # 50% en resistencia + trailing con el resto


class Clasificacion(str, Enum):
    """Clasificación de un ticker según el evaluador."""

    DAY = "DAY"
    SWING = "SWING"
    AMBIGUO = "AMBIGUO"  # empate — el trader decide
    DESCARTAR = "DESCARTAR"  # score muy bajo en ambos


class FuenteDatos(str, Enum):
    """Origen de los datos evaluados."""

    LIVE = "LIVE"        # datos de hoy via Schwab real
    MOCK = "MOCK"        # datos sintéticos (MOCK_SCHWAB=true) — nunca operar con esto
    HISTORICO = "HISTORICO"  # datos históricos para backtesting


# ============================================================================
# INGEST - CSV DE ToS
# ============================================================================


class TickerBasico(BaseModel):
    """Fila parseada del CSV de ThinkOrSwim."""

    ticker: str
    precio: float
    variacion_diaria_pct: float
    volumen_actual: int
    relvol: float
    atr_pct: float
    volumen_promedio: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    descripcion: Optional[str] = None
    market_cap_millones: Optional[float] = None


# ============================================================================
# CONFIGURACIÓN
# ============================================================================


class ScanConfig(BaseModel):
    """Configuración paramétrica completa del sistema.

    Esta es la única fuente de verdad para todos los parámetros.
    El evaluador, backtester y optimizador reciben siempre un ScanConfig completo.
    Nunca hardcodear umbrales o pesos en la lógica — siempre vienen de la config.
    """

    # Metadatos
    nombre: str = "default"
    descripcion: str = ""
    creada_en: datetime = Field(default_factory=datetime.utcnow)

    # ── Filtros de entrada (equivalentes a los filtros de ToS) ──────────────
    # No filtran el CSV en sí (ToS ya filtró), sino que validan que cada
    # ticker cumpla los mínimos antes de evaluarlo — si no, se descarta
    # directamente (ver evaluator._validar_filtros_entrada). Sirven también
    # de referencia para el backtesting histórico.
    precio_min: float = Field(5.0, gt=0)
    precio_max: float = Field(500.0, gt=0)
    volumen_promedio_min: int = Field(500_000, ge=0)
    float_min: int = Field(10_000_000, ge=0)
    variacion_diaria_min_pct: float = Field(2.0, ge=0)
    relvol_min: float = Field(1.5, ge=0)
    atr_pct_min: float = Field(2.0, ge=0)
    spread_max_pct: float = Field(1.0, ge=0)  # spread bid/ask máximo aceptable, % del precio

    # ── Umbrales de los criterios objetivos ─────────────────────────────────
    relvol_umbral_day: float = Field(3.0, gt=0)  # criterio 3: RelVol > X → day
    relvol_umbral_swing_min: float = Field(1.5, ge=0)  # criterio 3: RelVol entre X e Y → swing
    relvol_umbral_swing_max: float = Field(3.0, gt=0)
    atr_pct_umbral_day: float = Field(3.0, gt=0)  # criterio 4: ATR% > X → day
    atr_pct_umbral_swing_min: float = Field(1.5, ge=0)  # criterio 4: ATR% entre X e Y → swing
    atr_pct_umbral_swing_max: float = Field(3.0, gt=0)
    ivr_umbral_compra: float = Field(30.0, ge=0, le=100)  # criterio 6: IVR < X → señal day (opciones baratas)
    ivr_umbral_venta: float = Field(50.0, ge=0, le=100)   # criterio 6: IVR > X → señal swing (opciones caras)

    # ── Pesos de los 6 criterios objetivos ────────────────────────────────────
    # Valor 0.0 desactiva el criterio. Default 1.0 = peso igual para todos.
    # El "capital" no es un criterio puntuado — es un desempate aplicado en
    # evaluator._clasificar() cuando score_day == score_swing (ver CLAUDE.md).
    peso_timeframe_setup: float = Field(1.0, ge=0)  # criterio 1
    peso_catalizador: float = Field(1.0, ge=0)  # criterio 2
    peso_relvol: float = Field(1.0, ge=0)  # criterio 3
    peso_atr_pct: float = Field(1.0, ge=0)  # criterio 4
    peso_sma200: float = Field(1.0, ge=0)  # criterio 5
    peso_ivr: float = Field(1.0, ge=0)  # criterio 6

    # ── Umbral de decisión ──────────────────────────────────────────────────
    umbral_decision: float = Field(4.0, ge=0)  # score mínimo (sobre total ponderado) para clasificar

    # ── Gestión de posición ─────────────────────────────────────────────────
    modo_salida: ModoSalida = ModoSalida.FIXED_RR
    rr_target: float = Field(2.0, gt=0)  # solo aplica si modo = FIXED_RR
    stop_atr_multiplicador: float = Field(1.5, gt=0)
    target_atr_multiplicador: float = Field(3.0, gt=0)  # referencia si no hay nivel técnico claro
    trailing_activacion_r: float = Field(1.0, ge=0)  # mover stop a BE al alcanzar 1R
    trailing_lock_r: float = Field(2.0, ge=0)  # mover stop a +1R al alcanzar 2R
    riesgo_por_operacion_pct: float = Field(1.0, gt=0, le=100)
    perdida_maxima_diaria_pct: float = Field(3.0, gt=0, le=100)
    posiciones_simultaneas_max: int = Field(3, gt=0)

    # ── Períodos de cálculo de indicadores ──────────────────────────────────
    ema_rapida: int = Field(9, gt=0)
    ema_media: int = Field(21, gt=0)
    ema_lenta: int = Field(50, gt=0)
    sma_tendencia: int = Field(200, gt=0)
    rsi_periodo: int = Field(14, gt=0)
    atr_periodo: int = Field(14, gt=0)
    hv_periodo: int = Field(20, gt=0)  # ventana de volatilidad histórica realizada — proxy de IVR (ver criterio 6)
    macd_rapida: int = Field(12, gt=0)
    macd_lenta: int = Field(26, gt=0)
    macd_signal: int = Field(9, gt=0)
    bb_periodo: int = Field(20, gt=0)
    bb_desviacion: float = Field(2.0, gt=0)

    # ── Velas a descargar por timeframe ─────────────────────────────────────
    velas_5m: int = Field(78, gt=0)  # ~1 día de trading
    velas_15m: int = Field(100, gt=0)  # ~5 días
    velas_4h: int = Field(60, gt=0)  # ~3 meses
    velas_diarias: int = Field(252, gt=0)  # ~1 año

    # ── Períodos de cálculo de volumen ──────────────────────────────────────
    relvol_periodo: int = Field(50, gt=0)  # ventana de velas para calcular el promedio de RelVol

    # ── Guardia contra clasificaciones con datos insuficientes ───────────────
    # Si menos de N criterios pudieron calcularse → DESCARTAR automáticamente.
    # Evita falsa confianza cuando faltan datos (ej: sin opciones → IVR None).
    # Hay 6 criterios objetivos en total (ver criteria.py) — no puede pedirse más que eso.
    min_criterios_calculables: int = Field(4, ge=1, le=6)

    # ── Slippage para simulación realista ────────────────────────────────────
    # En day trading los fills perfectos sobreestiman retornos significativamente.
    # Aplica en entrada Y salida (ida y vuelta). Valor conservador: 5 bps por lado.
    slippage_bps: float = Field(5.0, ge=0)

    # ── Validaciones cruzadas entre campos relacionados ──────────────────────
    @model_validator(mode="after")
    def _validar_rangos_relacionados(self) -> "ScanConfig":
        if self.precio_min >= self.precio_max:
            raise ValueError("precio_min debe ser menor que precio_max")
        if self.relvol_umbral_swing_min >= self.relvol_umbral_swing_max:
            raise ValueError("relvol_umbral_swing_min debe ser menor que relvol_umbral_swing_max")
        if self.atr_pct_umbral_swing_min >= self.atr_pct_umbral_swing_max:
            raise ValueError("atr_pct_umbral_swing_min debe ser menor que atr_pct_umbral_swing_max")
        if self.ivr_umbral_compra >= self.ivr_umbral_venta:
            raise ValueError("ivr_umbral_compra debe ser menor que ivr_umbral_venta")
        return self


# ============================================================================
# RESULTADO DE SCAN
# ============================================================================


class ScanResult(BaseModel):
    """Resultado de evaluar un ticker en un momento dado."""

    id: Optional[int] = None

    # Identificación
    ticker: str
    fecha: date
    timestamp: datetime
    fuente: FuenteDatos

    # Snapshot de config usada — CRÍTICO para reproducibilidad
    # Se guarda como dict para no acoplar el modelo al schema de ScanConfig
    config_snapshot: dict

    # Versionado — permite detectar si un resultado antiguo es reproducible
    # con código nuevo. Incrementar evaluator_version en cada cambio de lógica.
    config_version: str = "1.0.0"  # SemVer del schema de ScanConfig
    evaluator_version: str = "1.2.0"  # SemVer del código del evaluador

    # ── Contexto de mercado al momento del scan ──────────────────────────────
    # No afecta el score. Input para el optimizador en Fase 2.
    # Si no están disponibles quedan None — nunca bloquean el scan.
    vix_apertura: Optional[float] = None  # VIX al momento del scan
    spy_sobre_sma200: Optional[bool] = None  # SPY sobre/bajo SMA 200
    futuros_es_gap_pct: Optional[float] = None  # gap % futuros ES pre-market
    calendar_disponible: bool = True  # False si el calendar no respondió

    # ── Métricas del CSV de ToS (o calculadas en backtesting) ────────────────
    precio: float
    variacion_diaria_pct: float
    relvol: float
    atr_pct: float
    volumen_actual: int

    # ── Señales técnicas calculadas ──────────────────────────────────────────
    sobre_sma200: Optional[bool] = None
    sobre_ema50: Optional[bool] = None
    cruce_ema_921_5m: Optional[bool] = None  # True=alcista, False=bajista
    cruce_ema_921_15m: Optional[bool] = None
    cruce_ema_921_4h: Optional[bool] = None
    cruce_ema_921_d: Optional[bool] = None
    rsi_14_5m: Optional[float] = None
    rsi_14_d: Optional[float] = None
    macd_cruce_alcista_15m: Optional[bool] = None
    macd_cruce_alcista_d: Optional[bool] = None

    # ── IVR (opciones) ───────────────────────────────────────────────────────
    ivr: Optional[float] = None  # HV Rank (proxy de IVR — ver pipeline._calcular_ivr)
    ivr_señal_day: Optional[bool] = None  # True si IVR no es determinante
    ivr_señal_swing: Optional[bool] = None  # True si IVR < 30% o > 50%

    # ── Catalizadores (del Trading Calendar) ─────────────────────────────────
    warning_calendar: Optional[str] = None  # "GREEN" | "YELLOW" | "RED"
    earnings_24h: bool = False
    evento_macro_24h: bool = False
    filing_8k_24h: bool = False
    upgrade_downgrade_24h: bool = False
    catalizador_detectado: bool = False  # OR de los anteriores

    # ── Output del evaluador ─────────────────────────────────────────────────
    score_day: float = 0.0  # suma ponderada de criterios → day
    score_swing: float = 0.0  # suma ponderada de criterios → swing
    score_max_posible: float = 0.0  # suma de todos los pesos (para normalizar)
    clasificacion: Clasificacion = Clasificacion.DESCARTAR
    confianza: float = 0.0  # score_winner / score_max_posible
    criterios_incompletos: list[str] = Field(default_factory=list)
    # criterios_incompletos: lista de criterios que no pudieron calcularse
    # (sin datos suficientes). Importante distinguir "criterio negativo" de
    # "criterio no calculable". Un criterio no calculable no penaliza el score.

    # ── Niveles de trading calculados ────────────────────────────────────────
    stop_loss_sugerido: Optional[float] = None
    target_sugerido: Optional[float] = None
    rr_calculado: Optional[float] = None

    # ── Resultado real — se completa post-operación para backtesting ─────────
    # Estos campos son None hasta que el trader registra el outcome
    operado: Optional[bool] = None
    precio_entrada: Optional[float] = None
    precio_salida: Optional[float] = None
    resultado_r: Optional[float] = None  # ganancia/pérdida en múltiplos de R
    resultado_usd: Optional[float] = None
    direccion_correcta: Optional[bool] = None
    notas: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# BACKTESTING
# ============================================================================


class BacktestRun(BaseModel):
    """Resultado de un run de backtesting."""

    id: Optional[int] = None

    # Config usada
    config_snapshot: dict
    config_nombre: str

    # Período
    fecha_inicio: date
    fecha_fin: date
    tickers: list[str]  # universo evaluado

    # Métricas agregadas
    total_señales: int
    total_operadas: int  # señales con clasificacion != DESCARTAR
    win_rate_day: float
    win_rate_swing: float
    rr_promedio_real: float
    rr_promedio_day: float
    rr_promedio_swing: float
    profit_factor: float  # sum(wins) / sum(losses)
    max_drawdown_pct: float
    sharpe_ratio: Optional[float] = None

    # Breakdown por clasificación
    señales_day: int
    señales_swing: int
    señales_ambiguo: int
    señales_descartadas: int

    # Breakdown por warning del calendar
    señales_green: int
    señales_yellow: int
    señales_red: int

    created_at: datetime = Field(default_factory=datetime.utcnow)
