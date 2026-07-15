# TRADING SCANNER SYSTEM — CLAUDE.md

Contexto persistente para el asistente de código. Leer completo antes de escribir cualquier línea.

---

## QUÉ ES ESTE PROYECTO

Sistema de scanning diario de acciones del mercado estadounidense (NYSE y NASDAQ) que:

1. **Ingiere** el universo de candidatos del día desde un CSV exportado de ThinkOrSwim (ToS)
2. **Enriquece** cada ticker con datos de la Schwab API (velas históricas, indicadores técnicos, quotes en tiempo real)
3. **Clasifica** cada acción como DAY trade o SWING trade usando un motor de evaluación paramétrico
4. **Integra** el warning de eventos del Trading Calendar (mismo servidor, localhost)
5. **Persiste** cada resultado con snapshot completo de la config para alimentar el backtesting
6. **Optimiza** la configuración de parámetros contra datos históricos para encontrar la mejor combinación para el perfil del trader

El scanner es el proyecto externo que consume el endpoint `/events/{ticker}/24h` del Trading Calendar.
Ambos proyectos corren en la misma PC. La comunicación es via HTTP a localhost.

El sistema está pensado para ser vendido/distribuido a clientes. La instalación tiene que ser
simple: doble click en setup.bat, completar credenciales en pantalla, listo. El usuario
nunca debe editar archivos manualmente.

---

## COMANDOS COMUNES

```bash
# Instalar dependencias
uv sync

# Arrancar el servidor (puerto 8001)
uv run uvicorn trading_scanner.main:app --host 0.0.0.0 --port 8001 --reload

# Correr todos los tests unitarios
uv run pytest tests/unit/ -v

# Correr un test específico
uv run pytest tests/unit/test_evaluator.py::test_pesos_afectan_score -v

# Correr solo tests que no requieren red
uv run pytest tests/unit/ -v -m "not integration and not slow"

# Modo mock sin Schwab ni Calendar (para desarrollo local)
MOCK_SCHWAB=true uv run uvicorn trading_scanner.main:app --host 0.0.0.0 --port 8001 --reload
```

### Notas de ejecución
- Los tests usan `pythonpath = ["."]` (ver `pyproject.toml`). Importar como `src.trading_scanner.X`.
- Con `MOCK_SCHWAB=true` el sistema genera OHLCV sintético reproducible (seeded por ticker) sin necesitar token Schwab ni Calendar corriendo.
- El token Schwab vive en `%APPDATA%/trading-scanner/schwab_token.json`, no en el repo.
- `backtest_data/` puede pesar varios GB — está en `.gitignore`.

---

## ESTADO ACTUAL DEL PROYECTO

```
Sprint 1 — Ingesta CSV + Schwab API + evaluador básico   [x] validado con datos reales
Sprint 2 — Dashboard + clasificación + integración cal.  [~] avanzado (falta streaming WebSocket)
Sprint 3 — Persistencia + backtesting                    [~] persistencia lista, backtesting sin empezar
Sprint 4 — Optimizador de parámetros                     [ ] pendiente
Sprint 5 — Integración Fase 3 (ejecución via Schwab API) [ ] pendiente (futuro lejano)
```

**Qué quedó realmente andando (validado con Schwab real conectado, no solo mock):**
- Ingesta de CSV de ToS robusta: normalización de nombres de columna (case/guion-bajo insensible),
  cascada de fallback para variación diaria (Change% → Net Chng → Extended Session % Change →
  Extended Session Net Change — ToS reporta 0 en columnas "Regular Trading Hours" durante pre-market),
  columnas opcionales (Bid/Ask/Description/Market Cap) para uso futuro.
- Conexión Schwab real vía flujo OAuth2 de webapp (`/schwab/connect`), sin `setup_wizard.py`
  (nunca se implementó, quedó solo documentado — ver sección de autenticación actualizada abajo).
- Badge de estado de conexión en el header (MOCK / ON_LINE / DESCONECTADO / SIN_CREDENCIALES),
  con verificación real contra Schwab (no solo que el token cargue), cache de 5 min, e inferencia
  de vencimiento por edad del token (~7 días) sin gastar llamadas a Schwab innecesariamente.
- Toggle de modo mock desde `/settings` sin reiniciar el servidor.
- Evaluador: además de los 7 criterios, un gate de **filtros de entrada** (`_validar_filtros_entrada`)
  que descarta tickers no operables (precio, volumen, ATR%, RelVol, spread bid/ask) antes de gastar
  los 7 criterios — ver sección del evaluador actualizada.
- `atr_pct`, `relvol` e IVR (proxy HV Rank) se calculan de las velas de Schwab, no del CSV — el CSV
  de ToS no siempre trae esas columnas confiablemente.
- Página de detalle por ticker (`/ticker/{ticker}`) con desglose de los 7 criterios recalculados
  desde el `config_snapshot` persistido.
- Página de Parámetros (`/config`) — formulario completo de `ScanConfig`, guarda en la tabla
  `scan_configs` de Turso; el pipeline usa `pipeline.get_active_config()` (última config guardada)
  en cada scan, no una copia fija al arrancar el servidor.

**Actualizar esta sección al completar cada sprint.**

---

## STACK — DECISIONES NO NEGOCIABLES

Cada elección está tomada. No proponer alternativas salvo que una librería esté deprecada o rota.

| Categoría | Usar | No usar | Por qué |
|-----------|------|---------|---------|
| Runtime | Python 3.12+ con uv | pip, conda, poetry | uv es más rápido, lockfile reproducible |
| HTTP cliente | httpx (async) | requests | async nativo, misma API, mantenido activamente |
| DataFrames | Polars | pandas | más rápido, mejor API, menos memoria |
| Base de datos | Turso vía HTTP API v2 (httpx) | libsql-experimental, SQLite local, PostgreSQL | misma decisión que el calendar — HTTP API v2 directamente |
| ORM | Pydantic BaseModel puro | SQLModel, SQLAlchemy | misma decisión que el calendar |
| Validación/Config | Pydantic v2 + pydantic-settings | dataclasses, marshmallow | estándar de facto |
| API | FastAPI | Flask, Django | async nativo, docs automáticas, tipado |
| Frontend | Jinja2 + HTMX | React, Vue, Next.js | sin build step, sin node_modules, servido desde FastAPI |
| CLI / setup | Typer | argparse, click | más limpio, basado en type hints |
| Output consola | Rich | print, logging básico | tablas, colores, progress bars |
| Schwab API | schwab-py | httpx directo, otras libs | librería oficial de la comunidad, mantenida activamente |
| Detección cambios | watchdog | polling manual, APScheduler | detección de filesystem events para el CSV de ToS |
| Indicadores técnicos | pandas-ta sobre Polars (via conversión puntual) | ta-lib (requiere C), otras | pandas-ta no requiere compilar binarios, funciona en Windows |
| Optimizador | Optuna | grid search manual, hyperopt | moderno, async-friendly, pruning inteligente |
| Cache histórico | Parquet local (via Polars) | Turso, SQLite, CSV | Turso tiene límite de 500MB — datos OHLCV históricos de 500 tickers en 4 timeframes superan ese límite fácilmente. Parquet comprime ~5x y Polars lo lee nativamente sin conversión |

---

## ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────┐
│         ToS — DISCOVERY ENGINE (en pantalla)            │
│   Stock Hacker con ThinkScript personalizado             │
│   Filtra ~8000 acciones → 10-30 candidatas              │
│   Export manual a CSV → carpeta watcheada               │
│   Durante sesión: nuevo export agrega candidatos        │
└──────────────────────────┬──────────────────────────────┘
                           │  CSV (pre-market + incremental durante sesión)
                           ▼
┌─────────────────────────────────────────────────────────┐
│              CSV WATCHER (watchdog)                      │
│   Detecta CSV nuevo en /input/                           │
│   PRE-MARKET: dispara pipeline completo REST + evaluación│
│   DURANTE SESIÓN: agrega tickers nuevos al WebSocket    │
│   sin reiniciar conexión ni re-evaluar los existentes   │
└──────────────────────┬───────────────────┬──────────────┘
                       │                   │
              PRE-MARKET (REST)    SESIÓN (WebSocket)
                       │                   │
                       ▼                   ▼
┌──────────────────────────┐  ┌────────────────────────────┐
│  SCHWAB REST API          │  │  SCHWAB STREAMING          │
│  schwab_history.py        │  │  schwab_stream.py          │
│  Una sola descarga por    │  │  NO IMPLEMENTADO todavía   │
│  ticker al inicio:        │  │  (Sprint 2 pendiente) —    │
│  - velas 5m/15m/4h/d     │  │  el dashboard hoy solo      │
│  - HV Rank (proxy IVR,   │  │  actualiza vía polling      │
│    no option chain real) │  │  HTMX cada 30s, no ticks   │
└──────────────┬────────────┘  └─────────────┬──────────────┘
               │                             │
               └──────────────┬──────────────┘
                              ▼
┌─────────────────────────────────────────────────────────┐
│           MARKET DATA CACHE (memoria)                    │
│   market_data_cache.py                                   │
│   Estado actual de cada ticker suscrito:                 │
│   - último precio, bid/ask, volumen acumulado           │
│   - velas del día construidas tick a tick               │
│   - VWAP intradiario calculado en tiempo real           │
│   - último snapshot de indicadores                      │
│   Si WebSocket se desconecta: mantiene último estado    │
│   conocido — el evaluador no se rompe                   │
└──────────────────────────┬──────────────────────────────┘
                           │  snapshot por ticker
                           ▼
┌─────────────────────────────────────────────────────────┐
│           TRADING CALENDAR (localhost:8000)              │
│   GET /events/{ticker}/24h → semáforo GREEN/YELLOW/RED  │
│   Catalizadores: earnings, macro, 8-K, upgrades         │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              EVALUATOR ENGINE (puro)                     │
│   - Recibe: snapshot del cache + eventos + ScanConfig   │
│   - Calcula: 7 criterios con pesos configurables        │
│   - Devuelve: score_day, score_swing, clasificación     │
│   - NO sabe si los datos son live o históricos          │
│   - Sin side effects — función pura y testeable         │
│   - Se re-ejecuta por eventos significativos:           │
│     cruce VWAP, cruce EMA, cambio RelVol, nuevo máximo  │
└──────────────────────────┬──────────────────────────────┘
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
┌──────────────────────┐   ┌──────────────────────────────┐
│   SCANNER LIVE       │   │   BACKTESTER                 │
│   Resultados del día │   │   Schwab histórico           │
│   se persisten en    │   │   datos 2020-hoy             │
│   Turso con snapshot │   │   misma config, mismo motor  │
└──────────┬───────────┘   └──────────────┬───────────────┘
           │                              │
           └──────────────┬───────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│                  TURSO (libSQL cloud)                    │
│   HTTP API v2 vía httpx │ Pydantic BaseModel puro       │
│   ScanResult │ ScanConfig │ BacktestRun                 │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  FASTAPI BACKEND                         │
│  POST /scan/upload        → recibir CSV de ToS          │
│  GET  /scan/latest        → último scan del día         │
│  GET  /scan/partial       → tabla HTMX (polling 30s)     │
│  GET  /scan/history       → historial de scans          │
│  GET  /ticker/{ticker}    → detalle + desglose criterios│
│  GET  /config             → form de ScanConfig activa   │
│  POST /config             → guardar y activar config    │
│  GET  /schwab/connect     → paso 1/2 login OAuth2 Schwab│
│  POST /schwab/connect     → completar login (pegar URL) │
│  GET  /settings           → credenciales + estado + mock│
│  POST /settings/mock      → toggle modo mock en caliente│
│                                                           │
│  Pendientes (Sprint 2/3/4):                              │
│  GET  /stream/status      → NO IMPLEMENTADO (sin stream) │
│  POST /backtest/run       → NO IMPLEMENTADO              │
│  GET  /optimize/run       → NO IMPLEMENTADO              │
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              FRONTEND (Jinja2 + HTMX)                   │
│  Dashboard diario │ Detalle por ticker │ Config         │
│  Scores actualizados vía HTMX polling ligero            │
│  Historial de scans │ Resultados backtesting            │
│  Estado del stream: tickers activos, última actualiz.   │
└─────────────────────────────────────────────────────────┘
```

---

## ESTRUCTURA DE DIRECTORIOS

```
trading-scanner/
│
├── CLAUDE.md                          ← este archivo
├── pyproject.toml                     ← dependencias con uv
├── uv.lock                            ← lockfile — siempre commitear
├── .python-version                    ← versión Python fijada
├── .gitignore
├── .env.example                       ← plantilla sin valores reales — sí al repo
├── .env                               ← credenciales reales — NUNCA al repo
├── README.md
│
├── setup.bat                          ← uv sync + copia .env.example → .env (sin wizard interactivo)
├── iniciar.bat                        ← arrancar el sistema diariamente (Windows)
├── actualizar.bat                     ← git pull + uv sync (Windows)
│
├── input/                             ← carpeta watcheada — ToS exporta acá
│   └── .gitkeep
│
├── backtest_data/                     ← cache local de datos históricos (NO al repo)
│   └── .gitkeep
│   # Estructura interna particionada para updates incrementales eficientes:
│   # backtest_data/{TICKER}/{timeframe}/{year}/{month}.parquet
│   # Ejemplo: backtest_data/AAPL/5m/2024/01.parquet
│   # Permite agregar nuevos meses sin reescribir archivos existentes
│
├── src/
│   └── trading_scanner/
│       ├── __init__.py
│       ├── config.py                  ← Pydantic Settings — credenciales + ScanConfig
│       ├── database.py                ← HTTP API v2 Turso — igual que el calendar
│       ├── models.py                  ← Pydantic BaseModel: ScanResult, ScanConfig, BacktestRun
│       ├── main.py                    ← FastAPI app + lifespan + CSV watcher
│       │
│       ├── ingest/
│       │   ├── csv_watcher.py         ← watchdog: detecta CSV nuevo en /input/
│       │   └── csv_parser.py          ← parsea el CSV de ToS → lista de tickers con métricas
│       │
│       ├── fetchers/
│       │   ├── schwab_client.py       ← auth OAuth2 (login webapp), token refresh, estado_conexion(),
│       │   │                            info_token(), horario hábil + feriados NYSE (vía Trading Calendar)
│       │   ├── schwab_history.py      ← REST API: velas históricas 5m/15m/4h/diario (Polars — ojo con
│       │   │                            `.group_by()`, no `.groupby()` que es API de pandas)
│       │   ├── schwab_options.py      ← REST API: option chain. get_ivr() real queda sin usar en el
│       │   │                            pipeline — Schwab no expone el rango de 52 semanas de IV
│       │   │                            implícita, solo IV actual y rango de 52 semanas de PRECIO.
│       │   ├── schwab_stream.py       ← NO IMPLEMENTADO — streaming WebSocket sigue siendo Sprint 2 pendiente
│       │   ├── market_data_cache.py   ← NO IMPLEMENTADO — depende de schwab_stream.py
│       │   ├── history_cache.py       ← existe, cache de Parquet — todavía no lo usa nada (backtest sin empezar)
│       │   └── calendar_client.py    ← GET localhost:8000/events/{ticker}/24h
│       │
│       ├── indicators/
│       │   ├── trend.py               ← EMA 9/21/50, SMA 200, VWAP, cruces
│       │   ├── momentum.py            ← RSI 14, MACD (12,26,9), Stochastic RSI
│       │   └── volume.py              ← RelVol, ATR%, volumen promedio, HV Rank (proxy de IVR), OBV
│       │
│       ├── engine/
│       │   ├── evaluator.py           ← motor puro: filtros de entrada + 7 criterios → score day/swing.
│       │   │                            `desglosar_criterios()` recalcula los 7 para auditar un ScanResult ya persistido
│       │   ├── criteria.py            ← los 7 criterios como funciones puras
│       │   └── signals.py             ← detección de señales técnicas (cruce EMA, ruptura, pullback)
│       │
│       ├── backtest/                  ← NO EXISTE TODAVÍA — Sprint 3 sin empezar
│       │
│       ├── optimizer/                 ← NO EXISTE TODAVÍA — Sprint 4 sin empezar
│       │
│       └── api/
│           ├── scan.py                ← scan (upload CSV, latest, partial, history) — usa
│           │                            pipeline.get_active_config(), no ScanConfig() fijo
│           ├── ticker.py              ← detalle por ticker + desglose de criterios
│           ├── config.py              ← GET/POST /config — form completo de ScanConfig,
│           │                            guarda en tabla scan_configs de Turso
│           ├── schwab.py              ← GET/POST /schwab/connect — flujo de login OAuth2 webapp
│           └── settings.py            ← credenciales + estado de servicios + toggle de modo mock
│
└── tests/
    └── unit/                          ← test_csv_parser.py, test_evaluator.py, test_criteria.py,
                                          test_indicators.py — no hay integration/ ni e2e/ todavía
│
├── templates/
│   ├── base.html                      ← layout con HTMX; header con badge MOCK/ON_LINE/DESCONECTADO
│   ├── dashboard.html                 ← tabla de candidatos del día con scores
│   ├── ticker_detail.html             ← detalle de un ticker: desglose de criterios + indicadores
│   ├── config.html                    ← formulario completo de ScanConfig (11 secciones)
│   ├── schwab_connect.html            ← flujo de login OAuth2 (paso 1 link, paso 2 pegar URL)
│   ├── history.html                   ← historial agrupado por fecha
│   └── settings.html                  ← credenciales + estado de servicios + toggle mock
│
└── static/
    └── htmx.min.js                    ← HTMX local, sin CDN externo
```

---

## MODELOS DE DATOS

### ScanConfig — configuración paramétrica completa

> **REGLA CRÍTICA:** `ScanConfig` es la única fuente de verdad para todos los parámetros del sistema.
> El evaluador, el backtester y el optimizador reciben siempre un objeto `ScanConfig` completo.
> Nunca hardcodear umbrales o pesos en la lógica — siempre vienen de la config.

```python
class ModoSalida(str, Enum):
    FIXED_RR     = "FIXED_RR"      # salir en target fijo (rr_target)
    TRAILING_EOD = "TRAILING_EOD"  # trailing stop hasta fin de sesión
    PARTIAL_SCALE = "PARTIAL_SCALE" # 50% en resistencia + trailing con el resto

class ScanConfig(BaseModel):
    # Metadatos
    nombre: str = "default"
    descripcion: str = ""
    creada_en: datetime = Field(default_factory=datetime.utcnow)

    # ── Filtros de entrada (equivalentes a los filtros de ToS) ──────────────
    # SÍ se aplican activamente — ver evaluator._validar_filtros_entrada().
    # No filtran el CSV en sí (ToS ya filtró), sino que descartan un ticker
    # directo (DESCARTAR, marcado FILTRO_ENTRADA:xxx) si no cumple el mínimo,
    # antes de gastar los 7 criterios. También sirven de referencia para el
    # backtesting histórico.
    precio_min: float = 5.0
    precio_max: float = 500.0
    volumen_promedio_min: int = 500_000
    float_min: int = 10_000_000
    variacion_diaria_min_pct: float = 2.0
    relvol_min: float = 1.5
    atr_pct_min: float = 2.0
    spread_max_pct: float = 1.0  # spread bid/ask máximo, % del precio — solo se evalúa si el CSV trae Bid/Ask

    # ── Umbrales de los criterios objetivos ─────────────────────────────────
    relvol_umbral_day: float = 3.0          # criterio 3: RelVol > X → day
    relvol_umbral_swing_min: float = 1.5    # criterio 3: RelVol entre X e Y → swing
    relvol_umbral_swing_max: float = 3.0
    atr_pct_umbral_day: float = 3.0         # criterio 4: ATR% > X → day
    atr_pct_umbral_swing_min: float = 1.5   # criterio 4: ATR% entre X e Y → swing
    atr_pct_umbral_swing_max: float = 3.0
    ivr_umbral_compra: float = 30.0  # criterio 6: HV Rank < X → señal day
    ivr_umbral_venta: float = 50.0   # criterio 6: HV Rank > X → señal swing

    # ── Pesos de los 7 criterios ─────────────────────────────────────────────
    # Valor 0.0 desactiva el criterio. Default 1.0 = peso igual para todos.
    peso_timeframe_setup: float = 1.0       # criterio 1
    peso_catalizador: float = 1.0           # criterio 2
    peso_relvol: float = 1.0               # criterio 3
    peso_atr_pct: float = 1.0              # criterio 4
    peso_sma200: float = 1.0               # criterio 5
    peso_ivr: float = 1.0                  # criterio 6 — en realidad pondera HV Rank, no IV Rank (ver más abajo)
    peso_capital: float = 1.0              # criterio 7

    # ── Umbral de decisión ──────────────────────────────────────────────────
    umbral_decision: float = 4.0  # score mínimo (sobre total ponderado) para clasificar

    # ── Gestión de posición ─────────────────────────────────────────────────
    modo_salida: ModoSalida = ModoSalida.FIXED_RR
    rr_target: float = 2.0                 # solo aplica si modo = FIXED_RR
    stop_atr_multiplicador: float = 1.5
    target_atr_multiplicador: float = 3.0  # referencia si no hay nivel técnico claro
    trailing_activacion_r: float = 1.0     # mover stop a BE al alcanzar 1R
    trailing_lock_r: float = 2.0           # mover stop a +1R al alcanzar 2R
    riesgo_por_operacion_pct: float = 1.0
    perdida_maxima_diaria_pct: float = 3.0
    posiciones_simultaneas_max: int = 3

    # ── Períodos de cálculo de indicadores ──────────────────────────────────
    ema_rapida: int = 9
    ema_media: int = 21
    ema_lenta: int = 50
    sma_tendencia: int = 200
    rsi_periodo: int = 14
    atr_periodo: int = 14
    hv_periodo: int = 20  # ventana de volatilidad histórica realizada — proxy de IVR (criterio 6)
    macd_rapida: int = 12
    macd_lenta: int = 26
    macd_signal: int = 9
    bb_periodo: int = 20
    bb_desviacion: float = 2.0

    # ── Velas a descargar por timeframe ─────────────────────────────────────
    velas_5m: int = 78        # ~1 día de trading
    velas_15m: int = 100      # ~5 días
    velas_4h: int = 60        # ~3 meses
    velas_diarias: int = 252  # ~1 año

    # ── Períodos de cálculo de volumen ───────────────────────────────────────
    relvol_periodo: int = 50  # ventana para RelVol y volumen promedio (ambos de velas diarias de Schwab)

    # ── Guardia contra clasificaciones con datos insuficientes ───────────────
    # Si menos de N criterios pudieron calcularse → DESCARTAR automáticamente.
    # Evita falsa confianza cuando faltan datos (ej: Schwab caído → sin velas
    # → ni ATR%/RelVol/HV Rank/cruces EMA se pueden calcular).
    min_criterios_calculables: int = 4

    # ── Slippage para simulación realista ────────────────────────────────────
    # En day trading los fills perfectos sobreestiman retornos significativamente.
    # Aplica en entrada Y salida (ida y vuelta). Valor conservador: 5 bps por lado.
    slippage_bps: float = 5.0
```

### ScanResult — resultado de evaluar un ticker

```python
class Clasificacion(str, Enum):
    DAY      = "DAY"
    SWING    = "SWING"
    AMBIGUO  = "AMBIGUO"   # empate — el trader decide
    DESCARTAR = "DESCARTAR" # score muy bajo en ambos

class FuenteDatos(str, Enum):
    LIVE      = "LIVE"       # datos de hoy via Schwab
    HISTORICO = "HISTORICO"  # datos históricos para backtesting

class ScanResult(BaseModel):
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
    config_version: str = "1.0.0"       # SemVer del schema de ScanConfig
    evaluator_version: str = "1.0.0"    # SemVer del código del evaluador

    # ── Contexto de mercado al momento del scan ──────────────────────────────
    # No afecta el score. Input para el optimizador en Fase 2.
    # Si no están disponibles quedan None — nunca bloquean el scan.
    vix_apertura: Optional[float] = None        # VIX al momento del scan
    spy_sobre_sma200: Optional[bool] = None     # SPY sobre/bajo SMA 200
    futuros_es_gap_pct: Optional[float] = None  # gap % futuros ES pre-market
    calendar_disponible: bool = True            # False si el calendar no respondió

    # ── Métricas del CSV de ToS (o calculadas en backtesting) ────────────────
    precio: float
    variacion_diaria_pct: float
    relvol: float
    atr_pct: float
    volumen_actual: int

    # ── Señales técnicas calculadas ──────────────────────────────────────────
    sobre_sma200: Optional[bool] = None
    sobre_ema50: Optional[bool] = None
    cruce_ema_921_5m: Optional[bool] = None   # True=alcista, False=bajista
    cruce_ema_921_15m: Optional[bool] = None
    cruce_ema_921_4h: Optional[bool] = None
    cruce_ema_921_d: Optional[bool] = None
    rsi_14_5m: Optional[float] = None
    rsi_14_d: Optional[float] = None
    macd_cruce_alcista_15m: Optional[bool] = None
    macd_cruce_alcista_d: Optional[bool] = None

    # ── IVR / HV Rank (criterio 6) ────────────────────────────────────────────
    # Schwab no expone el rango de 52 semanas de volatilidad IMPLÍCITA (solo
    # IV actual + rango de 52 semanas de PRECIO), así que esto en realidad es
    # HV Rank — volatilidad histórica de precio rankeada contra el último año
    # (ver indicators/volume.py::calc_hv_rank y pipeline.py::_calcular_ivr).
    ivr: Optional[float] = None
    ivr_señal_day: Optional[bool] = None   # True si IVR no es determinante
    ivr_señal_swing: Optional[bool] = None # True si IVR < 30% o > 50%

    # ── Catalizadores (del Trading Calendar) ─────────────────────────────────
    warning_calendar: Optional[str] = None  # "GREEN" | "YELLOW" | "RED"
    earnings_24h: bool = False
    evento_macro_24h: bool = False
    filing_8k_24h: bool = False
    upgrade_downgrade_24h: bool = False
    catalizador_detectado: bool = False     # OR de los anteriores

    # ── Output del evaluador ─────────────────────────────────────────────────
    score_day: float = 0.0          # suma ponderada de criterios → day
    score_swing: float = 0.0        # suma ponderada de criterios → swing
    score_max_posible: float = 0.0  # suma de todos los pesos (para normalizar)
    clasificacion: Clasificacion = Clasificacion.DESCARTAR
    confianza: float = 0.0          # score_winner / score_max_posible
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
    resultado_r: Optional[float] = None        # ganancia/pérdida en múltiplos de R
    resultado_usd: Optional[float] = None
    direccion_correcta: Optional[bool] = None
    notas: Optional[str] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### BacktestRun — resultado de un run de backtesting

```python
class BacktestRun(BaseModel):
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
    total_operadas: int        # señales con clasificacion != DESCARTAR
    win_rate_day: float
    win_rate_swing: float
    rr_promedio_real: float
    rr_promedio_day: float
    rr_promedio_swing: float
    profit_factor: float       # sum(wins) / sum(losses)
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
```

---

## EL EVALUADOR — REGLAS DE IMPLEMENTACIÓN

El `evaluator.py` es el componente más crítico del sistema. Estas reglas son no negociables:

**Regla 1 — Función pura:**
```python
def evaluar(datos: DatosTickerCompletos, config: ScanConfig) -> ScanResult:
    ...
```
Sin acceso a base de datos, sin llamadas HTTP, sin side effects. Recibe datos y config, devuelve resultado. Esto garantiza que live y backtesting usen exactamente el mismo código.

**Regla 2 — Criterios incompletos no penalizan:**
Si un criterio no puede calcularse (datos insuficientes, API no respondió, ticker sin opciones), se agrega a `criterios_incompletos` y NO se descuenta del score. El score se normaliza contra `score_max_posible` que solo incluye criterios que sí pudieron calcularse.

**Regla 3 — Score normalizado:**
```
score_day = suma de (peso_criterio_i * valor_criterio_i_day)
            para cada criterio i que pudo calcularse

confianza = score_winner / score_max_posible
```
Un ticker con 5 criterios calculados y score 4/5 es más confiable que uno con 7 criterios y score 4/7.

**Regla 4 — Los 7 criterios como funciones separadas:**
Cada criterio vive en `criteria.py` como función independiente y testeable:
```python
def criterio_relvol(relvol: float, config: ScanConfig) -> tuple[float, float]:
    # returns (score_day, score_swing) — cada uno entre 0.0 y 1.0
    ...

def criterio_atr_pct(atr_pct: float, config: ScanConfig) -> tuple[float, float]:
    ...
```

**Regla 5 — Umbral mínimo de criterios calculables:**
```
Si len(criterios_calculados) < config.min_criterios_calculables:
    clasificacion = DESCARTAR
    criterios_incompletos.append("INSUFICIENTE_DATA")
    return resultado  # no calcular score
```
Un ticker con 1 criterio calculado y score 0.9/1.0 es más peligroso que uno con
score 3.5/7.0 — la confianza alta con datos insuficientes es peor que la incertidumbre.

**Regla 5.5 — Filtros de entrada antes de los 7 criterios:**
```python
def _validar_filtros_entrada(datos: DatosTickerCompletos, config: ScanConfig) -> list[str]:
    # precio, variación diaria, ATR%, RelVol, volumen promedio, spread bid/ask
    # devuelve la lista de nombres de filtros violados (vacía = pasa)
```
Corre **antes** de los 7 criterios (antes incluso de la Regla 5). Si el ticker no cumple algún
mínimo de `ScanConfig` (`precio_min/max`, `variacion_diaria_min_pct`, `atr_pct_min`, `relvol_min`,
`volumen_promedio_min`, `spread_max_pct`), se descarta directo con `criterios_incompletos =
["FILTRO_ENTRADA:xxx", ...]`, sin gastar los 7 criterios. Si un dato puntual no está disponible
(ej. sin Bid/Ask en el CSV), ese filtro en particular simplemente no se evalúa — no bloquea por
ausencia de dato, solo por violación real de un dato que sí existe. Ejemplo real: un ADR de baja
liquidez con spread bid/ask >2% del precio se descartaba igual con los 7 criterios "viendo bien"
técnicamente — este gate existe específicamente para atrapar ese caso.

**Regla 6 — Clasificación por umbral relativo:**
```
score_day_ponderado   = score_day   * peso_total_calculable
score_swing_ponderado = score_swing * peso_total_calculable

si score_day_ponderado >= umbral_decision Y score_day > score_swing:
    clasificacion = DAY
elif score_swing_ponderado >= umbral_decision Y score_swing > score_day:
    clasificacion = SWING
elif ambos >= umbral_decision:
    clasificacion = AMBIGUO
else:
    clasificacion = DESCARTAR
```

---

## FLUJO DE INGESTA DEL CSV

### Cómo llega realmente el CSV — no hay export directo desde ToS

ThinkOrSwim **no permite descargar/exportar** los resultados del Stock Hacker directamente. El
flujo real del trader es: seleccionar todas las filas del scan, copiar, pegar en Notepad, agregar
a mano una primera fila con los nombres de columna (en el mismo orden que las columnas configuradas
en la grilla de ToS), y guardar como `.csv`. Es tab-separado (lo que ToS pega), y a simple vista en
Notepad las columnas casi nunca quedan alineadas visualmente — es normal, Notepad usa tabs de ancho
fijo mientras el texto de cada celda tiene largo distinto. Lo que importa es que cada fila tenga la
misma cantidad de tabs en el mismo orden que el header, no cómo se ve en pantalla.

### Columnas — obligatorias vs opcionales vs con fallback

Obligatorias: `Symbol`, `Last`, `Volume`. Además se necesita **al menos una** columna de variación
diaria (ver cascada abajo) o `parse_csv()` lanza `ValueError` explícito en vez de seguir con todo en 0.0.

**Columnas recomendadas (no obligatorias, pero hoy se usan)**: `Description`, `Bid`, `Ask`, `Market Cap`,
`Vol Index` (alias de Rel Volume). `ATR%`/`Avg Volume` **ya no hace falta** que estén en el CSV — se
calculan de las velas de Schwab (ver "El evaluador" más abajo), el CSV solo los usa como fallback si
Schwab no responde.

**Cascada de fallback para variación diaria** (`csv_parser._variacion_diaria`) — ToS reporta 0 en
columnas de "Regular Trading Hours" durante pre-market (la sesión regular todavía no arrancó):
1. `Change%` (Regular Trading Hours) — sirve una vez abierto el mercado.
2. `Net Chng` (regular) reconstruido con `Last`: `precio_anterior = Last - NetChng`.
3. `Extended Session Percent Change` — pensada específicamente para pre-market/after-hours.
4. `Extended Session Net Change` reconstruido con `Last`, igual que el punto 2.

**Normalización de nombres de columna** (`_normalize_alias`): case-insensitive y trata `_` y espacio
como equivalentes. El usuario puede escribir `Vol Index`, `vol_index` o `VOL_INDEX` en el header que
arma a mano — cualquiera funciona, no hace falta coincidencia exacta con el nombre "oficial" de ToS.
También tolera nombres acortados de las columnas Extended Session (ej. sin la palabra final "Change").

El `csv_parser.py` devuelve una lista de `TickerBasico`:

```python
class TickerBasico(BaseModel):
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
    market_cap_millones: Optional[float] = None  # parsea sufijos M/B de ToS
```

### CSV Watcher

`csv_watcher.py` usa `watchdog` para monitorear la carpeta `/input/`.
Al detectar un archivo `.csv` nuevo:
1. Espera a que el archivo sea estable — polling de tamaño hasta que no cambie en 500ms
   (el "esperar N segundos fijo" es frágil bajo carga o CSVs grandes):
   ```python
   async def wait_for_stable(path: Path, timeout_sec: int = 10) -> None:
       last_size, elapsed = -1, 0
       while elapsed < timeout_sec:
           await asyncio.sleep(0.5)
           current_size = path.stat().st_size
           if current_size == last_size and current_size > 0:
               return
           last_size, elapsed = current_size, elapsed + 0.5
       raise TimeoutError(f"CSV no estabilizado en {timeout_sec}s: {path}")
   ```
2. Valida cabeceras con Pydantic estricto — si faltan columnas esperadas, abortar con log claro
3. Parsea el CSV
3. Dispara el pipeline completo de forma asíncrona
4. Mueve el archivo a `/input/processed/` con timestamp

El usuario nunca tiene que hacer nada en el dashboard para iniciar el scan — exportar el CSV de ToS es suficiente.

---

## INTEGRACIÓN CON EL TRADING CALENDAR

El calendar corre en `localhost:8000`. El scanner llama a `localhost:8001` (o el puerto que use).

```python
# calendar_client.py
async def get_warning(ticker: str) -> CalendarWarning:
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://localhost:8000/events/{ticker}/24h")
        ...
```

Si el calendar no está corriendo, el scanner continúa sin esa información.
Los campos `warning_calendar` y catalizadores quedan en None y se agregan a `criterios_incompletos`.
**Nunca bloquear el scan por falta del calendar.**

**Segundo uso del Calendar — feriados NYSE para el horario hábil de Schwab:**
```python
# schwab_client.py
GET {calendar_base_url}/calendar/holidays/{year}  →  {"year": 2026, "holidays": ["2026-01-01", ...]}
```
Usado por `_en_horario_habil()` para decidir si vale la pena verificar la conexión Schwab en vivo
(ver "Autenticación Schwab" arriba). Mismo principio de resiliencia: si el Calendar no responde,
cae a una lista fija local (`FERIADOS_NYSE_FALLBACK`) — nunca bloquea. Otros endpoints de Calendar
disponibles pero sin usar todavía en el scanner: `/calendar/is-business-day/{date}`,
`/calendar/next-business-day/{date}`, `/calendar/prev-business-day/{date}`,
`/calendar/add-business-days/{date}/{n}` (`_check_calendar()` en `api/settings.py` usa
`is-business-day` solo como health-check liviano, no `/health` — ese endpoint no existe en Calendar).

---

## MODOS DE OPERACIÓN — REST vs STREAMING

El scanner opera en dos modos distintos según el momento del día.
Nunca mezclar ambos modos para el mismo propósito — cada uno tiene una función específica.

### Modo PRE-MARKET (REST API)

Corre una sola vez cuando llega el CSV de ToS. Para cada ticker:

```
1. schwab_history.py  → descarga velas 5m/15m/4h/diarias (una sola vez)
2. schwab_options.py  → descarga option chain → calcula IVR (una sola vez)
3. calendar_client.py → obtiene warning y catalizadores (una sola vez)
4. indicators/        → calcula todos los indicadores sobre el histórico
5. evaluator.py       → genera clasificación inicial + score day/swing
6. market_data_cache  → inicializa estado del ticker con datos históricos
7. schwab_stream.py   → suscribe el ticker al WebSocket
```

Al final del pipeline pre-market, todos los tickers están:
- evaluados con su clasificación inicial
- visibles en el dashboard
- suscritos al stream para actualizaciones en tiempo real

### Modo SESIÓN (WebSocket Streaming)

Una conexión WebSocket persistente recibe ticks de todos los tickers suscritos.
Por cada tick recibido:

```
1. market_data_cache actualiza: precio, bid/ask, volumen, construye vela actual
2. Detectar si el tick generó un evento significativo:
   - ¿cruzó VWAP? → re-evaluar
   - ¿cruzó EMA 9 o 21? → re-evaluar
   - ¿RelVol cambió de categoría (pasó umbral)? → re-evaluar
   - ¿nuevo máximo/mínimo del día? → re-evaluar
3. Si hay evento significativo → llamar evaluator.py con snapshot del cache
4. Si el score cambió materialmente (> 0.15 puntos) → actualizar dashboard
```

No re-evaluar en cada tick — solo en eventos significativos.
Re-evaluar en cada tick bloquearía el event loop y no agrega valor.

### Descubrimiento incremental durante sesión

Si ToS exporta un segundo CSV durante la sesión (nueva oportunidad intradiaria):

```
csv_watcher detecta CSV nuevo
    ↓
Identifica tickers que NO están en la suscripción activa
    ↓
Para cada ticker nuevo: corre pipeline pre-market completo
    ↓
Suscribe al WebSocket existente (sin reiniciar la conexión)
    ↓
Los tickers ya suscritos no se tocan
```

### Market Data Cache — estructura

```python
@dataclass
class TickerCache:
    ticker: str
    ultimo_precio: float
    bid: float
    ask: float
    volumen_acumulado: int
    vwap: float                          # recalculado en cada tick
    velas_hoy: list[Vela]                # velas del día construidas tick a tick
    ultimo_snapshot_indicadores: dict    # último cálculo completo de indicadores
    ultimo_score_day: float
    ultimo_score_swing: float
    ultima_clasificacion: str
    ultima_evaluacion: datetime
    suscrito_en: datetime

class MarketDataCache:
    # Dict en memoria — NO persiste a Turso durante la sesión
    # Al cierre del día, el último ScanResult ya fue persistido
    _cache: dict[str, TickerCache] = {}

    def actualizar_tick(self, ticker: str, precio: float, ...) -> bool:
        # Retorna True si el tick generó un evento significativo
        ...

    def snapshot(self, ticker: str) -> DatosTickerCompletos:
        # Genera el objeto que recibe el evaluador
        ...
```

### Reconexión automática del WebSocket

Si el WebSocket se desconecta (pérdida de red, timeout de Schwab):

```
1. market_data_cache mantiene el último estado conocido
2. schwab_stream intenta reconectar con backoff exponencial
3. El dashboard muestra indicador "stream reconectando..."
4. Al reconectar: re-suscribe todos los tickers del cache
5. El evaluador no se toca — sigue funcionando con datos del cache
```

---

## AUTENTICACIÓN SCHWAB

> **`setup_wizard.py` documentado en versiones anteriores de este archivo NUNCA se implementó.**
> El flujo real es el que sigue — vía web, integrado al dashboard, no vía CLI/wizard de instalación.

schwab-py no soporta un flujo de login automático viable dentro de un handler async de FastAPI
(`client_from_login_flow` es bloqueante, levanta un servidor local y abre un browser controlado por
la librería). Se usa en cambio el par de funciones que schwab-py expone explícitamente para
integrarse en workflows de webapp:

```
GET  /schwab/connect  → genera authorization_url (schwab_auth.get_auth_context), la muestra al
                         usuario para que haga login + 2FA en una pestaña nueva
POST /schwab/connect  → el usuario pega la URL de redirect completa (aunque el browser muestre
                         error de conexión al llegar a la URL de callback, es esperado — no hay
                         nada corriendo ahí). schwab_auth.client_from_received_url() intercambia
                         el code por el token y lo persiste.
```

Implementado en `fetchers/schwab_client.py` (`iniciar_conexion()`, `completar_conexion()`) y
`api/schwab.py`. Errores esperables al pegar una URL vieja/repetida: `MismatchingStateError`
(el `state` OAuth no coincide — pasa si se recarga `/schwab/connect` entre el paso 1 y el paso 2,
generando un link nuevo con `state` distinto al que finalmente se pega).

**Vencimiento del token — no lo documenta oficialmente Schwab:** el `refresh_token` deja de ser
aceptado por Schwab ~7 días después de la autorización manual (confirmado empíricamente: un token
de 21 días fue rechazado con `invalid_grant`). `REFRESH_TOKEN_MAX_AGE_DIAS = 7` en `schwab_client.py`
infiere el vencimiento por la edad del token (guardada en `creation_timestamp` dentro del propio
archivo del token) **sin gastar una llamada a Schwab** para tokens ya sabidos vencidos.

**Estado de conexión (`estado_conexion()`)** — única fuente de verdad, usada por el badge del header
en todas las páginas: `"MOCK"` | `"SIN_CREDENCIALES"` | `"ON_LINE"` | `"DESCONECTADO"`. Hace una
llamada real y liviana (`client.get_account_numbers()` — solo hashes de cuenta, sin saldos/posiciones)
para confirmar que Schwab acepta el token, no solo que el archivo cargue. Esto tiene 3 capas de
protección contra golpear a Schwab de más:
1. Si el token ya tiene ≥7 días, ni siquiera intenta la llamada real (ver arriba).
2. Cache de 5 minutos (`_ESTADO_CACHE_TTL`) — no repite la llamada real en cada carga de página.
3. Fuera de horario hábil (ver más abajo), no refresca el cache aunque haya vencido — reusa el
   último valor conocido sin tocar la red.

**Horario hábil (`_en_horario_habil()`)** — ventana 7:00–17:00 hora de Nueva York (`ZoneInfo`,
evita calcular a mano el offset con Argentina que cambia con el horario de verano/invierno de
EE.UU.), lunes a viernes, sin feriados NYSE. Los feriados se consultan a Trading Calendar
(`GET {calendar_base_url}/calendar/holidays/{year}`, cacheado por año en memoria) con fallback a
una lista fija local (`FERIADOS_NYSE_FALLBACK`) si el Calendar no responde — mismo principio que
`calendar_client.py`: nunca bloquear por su ausencia.

**El token de Schwab NUNCA va al repositorio.** Se guarda en `%APPDATA%/trading-scanner/schwab_token.json`
(Windows). Usar `%APPDATA%` y no la carpeta del proyecto es una buena práctica de seguridad en Windows
— evita exposición accidental aunque `.gitignore` esté mal configurado.

```python
# schwab_client.py — ruta del token
TOKEN_PATH = Path(os.environ["APPDATA"]) / "trading-scanner" / "schwab_token.json"
TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
```

---

## CONFIGURACIÓN Y CREDENCIALES

### Variables de entorno (.env)

```bash
# Turso — base de datos cloud (obligatorio)
TURSO_DATABASE_URL=libsql://[nombre].turso.io
TURSO_AUTH_TOKEN=

# Schwab API (obligatorio)
SCHWAB_APP_KEY=
SCHWAB_APP_SECRET=
SCHWAB_CALLBACK_URL=https://127.0.0.1

# Trading Calendar — URL base (default localhost)
CALENDAR_BASE_URL=http://localhost:8000

# Puerto del scanner
SCANNER_PORT=8001

# Carpeta de input para CSV de ToS
INPUT_FOLDER=./input

# Modo mock: datos OHLCV sintéticos, sin necesitar Schwab real (default false)
# También se puede togglear en caliente desde /settings sin editar .env ni reiniciar
MOCK_SCHWAB=false
```

### Pydantic Settings — config.py

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    turso_database_url: str = ""
    turso_auth_token: str = ""
    schwab_app_key: str = ""
    schwab_app_secret: str = ""
    schwab_callback_url: str = "https://127.0.0.1"
    calendar_base_url: str = "http://localhost:8000"
    scanner_port: int = 8001
    input_folder: str = "./input"
    mock_schwab: bool = False

settings = Settings()
```

---

## BACKTESTING — CONSIDERACIONES DE IMPLEMENTACIÓN

### Fuente de datos históricos

Schwab API provee velas históricas hasta varios años atrás en todos los timeframes.
El backtester usa `schwab_history.py` con las mismas funciones que el scanner live,
pasando fechas históricas en lugar de "hoy".

### Estrategia de testing

El evaluador es una función pura — es el componente más crítico y el más fácil de testear.
Tests obligatorios antes de considerar Sprint 1 completo:

```
tests/unit/test_criteria.py        → cada criterio con inputs conocidos → output esperado
tests/unit/test_evaluator_logic.py → clasificación DAY/SWING/AMBIGUO/DESCARTAR
tests/unit/test_config_validation.py → ScanConfig rechaza valores inválidos (pesos negativos, etc.)
tests/e2e/test_csv_to_result.py    → CSV fixture → ScanResult completo (sin llamadas reales)
```

Configuración en `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "unit: pruebas unitarias puras — sin red, sin archivos",
    "integration: requieren Schwab sandbox o Turso test",
    "slow: backtesting completo — ejecutar manualmente",
]
```

Los tests de integración (`@pytest.mark.integration`) nunca corren en CI automático.
Los tests unitarios deben ser instantáneos — si tardan más de 1 segundo, hay un problema de diseño.

---

### Cache de datos históricos — Parquet local

Los datos OHLCV históricos se cachean localmente en formato Parquet para evitar
llamadas repetidas a Schwab durante el backtesting y el optimizador.

**Por qué Parquet y no Turso:**
El tier gratuito de Turso tiene 500MB de límite. Los datos OHLCV de un universo
razonable (500 tickers × 4 timeframes × 1 año) superan ese límite holgadamente
solo en el timeframe de 5 minutos. Parquet comprime ~5x y Polars lo lee nativamente.

**Estructura de archivos — particionada para updates incrementales:**
```
backtest_data/
    AAPL/
        5m/2024/01.parquet   ← enero 2024
        5m/2024/02.parquet   ← febrero 2024 (append sin reescribir enero)
        15m/2024/01.parquet
        4h/2024/01.parquet
        d/2024/01.parquet
    MSFT/
        5m/2024/01.parquet
        ...
```
La partición por `ticker/timeframe/year/month/` permite agregar datos nuevos sin reescribir
archivos existentes, hacer pruning de meses viejos de forma quirúrgica, y leer rangos
parciales sin cargar el año completo en memoria.

**`history_cache.py` — interfaz única para datos históricos:**
```python
async def get_history(
    ticker: str,
    timeframe: str,       # "5m" | "15m" | "4h" | "d"
    fecha_inicio: date,
    fecha_fin: date,
) -> pl.DataFrame:
    # 1. Busca en backtest_data/ si existe el parquet para ese período
    # 2. Si existe y está completo → leer parquet (sin API call)
    # 3. Si no existe o está incompleto → llamar schwab_history.py → guardar parquet
    # 4. Devuelve siempre el mismo DataFrame independientemente de la fuente
```

El backtester y el optimizador nunca llaman a `schwab_history.py` directamente.
Siempre usan `history_cache.py`. El scanner live llama a `schwab_history.py` directamente
(no necesita cache — siempre quiere datos frescos de hoy).

**Metadatos del cache — sí en Turso:**
Una tabla liviana `history_cache_meta` registra qué datos están cacheados:
```
ticker | timeframe | fecha_inicio | fecha_fin | archivo | descargado_en
```
Esto permite saber si hay que ir a la API o si el parquet ya existe y es suficiente.

**La carpeta `backtest_data/` va en `.gitignore`** — puede pesar varios GB con el tiempo.

Los datos históricos de Schwab solo tienen acciones que todavía existen o cotizan.
Acciones que quebraron o fueron deslistadas no aparecen. Esto es un sesgo conocido
que hay que documentar en los resultados del backtester. **No intentar corregirlo en el MVP**
— es aceptable para calibración de parámetros, no para auditoría de retornos absolutos.

### Universo histórico

El backtester no puede re-correr el scanner de ToS sobre datos históricos.
El universo para backtesting se construye de dos formas:
1. **Universo real:** los tickers que salieron en los CSVs históricos guardados (si el trader ya viene usando el sistema)
2. **Universo proxy:** lista de los 500 tickers más líquidos del S&P 500 + Russell 1000 para los períodos anteriores al sistema

### Simulación de gestión de posición

`simulator.py` simula el resultado de una señal dados los modos de salida configurables:

```
FIXED_RR:
  → entrada en precio de apertura siguiente vela
  → stop en precio - (ATR * stop_atr_multiplicador)
  → target en precio + (stop_distancia * rr_target)
  → resultado: ganó target, tocó stop, o cerró EOD sin resolver

TRAILING_EOD:
  → entrada en apertura
  → trailing stop ajustado en cada vela
  → cierre obligatorio a las 3:55pm ET
  → resultado: precio de cierre del trailing o EOD

PARTIAL_SCALE:
  → 50% sale en primera resistencia calculada
  → 50% con trailing hasta EOD o hasta trailing tocado
  → resultado: promedio ponderado de las dos salidas
```

---

## SCANNER DE ToS — SIN ThinkScript, WORKFLOW MANUAL

> **`tos_scanner.ts` documentado en versiones anteriores de este archivo NUNCA se creó.**
> ToS no permite exportar el Stock Hacker directamente (ver "Cómo llega realmente el CSV" arriba) —
> el trader configura las columnas de la grilla a mano en ToS, copia/pega a Notepad, agrega el
> header manualmente y guarda como `.csv`. No hay ThinkScript que generar ni sincronizar.

**Columnas recomendadas para configurar en la grilla del Stock Hacker** (nombres tal cual los usa
ToS por default — el parser tolera mayúsculas/minúsculas y `_` en vez de espacio si el trader
renombra la columna al armar el header a mano):

```
Symbol, Description, Last, Extended Session Percent Change, Extended Session Net Change,
Volume, Bid, Ask, Vol Index, Market Cap
```

Los filtros de calidad de candidatos (precio, volumen, ATR%, RelVol, variación diaria) los aplica
el Stock Hacker de ToS del lado del trader (fuera del alcance de este repo), y el scanner los
**vuelve a validar** él mismo con `ScanConfig` como red de seguridad (`evaluator._validar_filtros_entrada`,
ver más arriba) — por si el scan de ToS quedó mal configurado o algún candidato se cuela igual.

---

## DECISIONES DE IMPLEMENTACIÓN NO NEGOCIABLES

- **No usar pandas** — siempre Polars. La única excepción es `pandas-ta` para indicadores, que se usa con conversión puntual (Polars → pandas → Polars) y se aisla en `indicators/`.
- **No llamadas síncronas en rutas FastAPI** — usar `asyncio.to_thread()` si es necesario.
- **No hardcodear umbrales** — todo viene de `ScanConfig`.
- **No modificar `config_snapshot`** después de guardado — es inmutable por diseño.
- **No bloquear el scan** si el Trading Calendar no responde — degradar gracefully.
- **No guardar el token de Schwab en el repo** — `.schwab_token.json` siempre en `.gitignore`.
- **No commitear `backtest_data/`** — puede pesar varios GB, va en `.gitignore`.
- **No correr el optimizador en producción** — Optuna consume CPU intensivamente, tiene su propio comando separado.
- **No optimizar pesos en la primera fase de Optuna** — dejar todos los `peso_*` en 1.0 y optimizar solo
  umbrales (`relvol_umbral_day`, `atr_pct_umbral_day`, etc.), `rr_target`, `stop_atr_multiplicador` y `slippage_bps`.
  Los pesos crean un espacio de búsqueda enorme que genera overfitting severo antes de tener suficientes datos reales.
  Activar la optimización de pesos solo después de 60+ días de operación real registrada.
- **No escribir tests que dependan de Schwab en CI** — marcarlos con `@pytest.mark.integration` y excluirlos del pipeline automático.
- **No promediar posiciones perdedoras** — esto es un sistema de trading, no un banco central.

---

## LO QUE NO HACER — REGLAS ABSOLUTAS

- **No usar requests** — siempre httpx async
- **No crear SQLite local** — siempre Turso (libSQL cloud)
- **No pedirle al usuario que edite .env manualmente** — usar `/settings` (credenciales) o `/config`
  (parámetros de `ScanConfig`, guardados en Turso vía `/config`, no en `.env`)
- **No mostrar tokens o credenciales completos en pantalla** — solo últimos 4 caracteres
- **No duplicar la lógica de eventos** — siempre consultar el Trading Calendar via HTTP
- **No instalar npm ni crear package.json** — HTMX se incluye como archivo estático local
- **No ejecutar órdenes reales** hasta Sprint 5 — este sistema es análisis, no ejecución
- **No hacer polling continuo a Schwab** — usar WebSocket streaming para datos en tiempo real durante la sesión
- **No llamar REST API de Schwab durante la sesión para quotes** — eso es trabajo del WebSocket streaming
- **No re-evaluar el evaluador en cada tick** — solo en eventos significativos (cruce VWAP, cruce EMA, cambio RelVol)
- **No reiniciar el WebSocket al llegar un CSV nuevo durante sesión** — agregar tickers nuevos a la suscripción existente
- **No mezclar lógica live y backtesting en el evaluador** — el evaluador es puro y agnóstico

---

## CONTEXTO DE NEGOCIO ÚTIL PARA DECISIONES DE CÓDIGO

- El trader usa ThinkOrSwim en la misma PC donde corre el sistema
- El Trading Calendar ya está en producción en `localhost:8000`
- El scanner corre en `localhost:8001`
- La watchlist tiene entre 5 y 30 tickers típicamente después del filtro de ToS
- El sistema está diseñado para ser vendido/distribuido — la UX del usuario final no técnico importa
- El usuario final nunca debe tocar archivos de configuración manualmente
- El backtesting es la herramienta de mejora continua del sistema — sin él no hay calibración
- Un warning RED del calendar no prohíbe operar — condiciona la estrategia a opciones con riesgo máximo definido
- La preservación del capital es prioridad absoluta sobre la frecuencia de operaciones
