# Trading Scanner

Sistema de scanning diario de acciones del mercado estadounidense (NYSE y NASDAQ) que ingiere candidatos desde ThinkOrSwim, los enriquece con datos de la Schwab API, y los clasifica como DAY o SWING trades.

## Lectura Obligatoria

Antes de trabajar en este proyecto, **lee completamente el archivo `CLAUDE.md`** en la raíz. Contiene:

- Arquitectura del sistema
- Stack de decisiones no negociables
- Modelos de datos Pydantic
- Reglas de implementación críticas
- Lo que SÍ y lo que NO hacer

## Instalación Rápida (Windows)

```batch
setup.bat
```

Esto hará:
1. Verificar que `uv` está instalado (instálalo desde https://docs.astral.sh/uv/)
2. Crear `.env` desde `.env.example`
3. Instalar todas las dependencias con `uv sync`
4. Crear directorios necesarios

## Configuración

### 1. Edita `.env` con tus credenciales

```env
# Turso Database (libSQL cloud)
TURSO_DATABASE_URL=libsql://[your-database].turso.io
TURSO_AUTH_TOKEN=[your-token]

# Schwab API
SCHWAB_APP_KEY=[your-key]
SCHWAB_APP_SECRET=[your-secret]
SCHWAB_CALLBACK_URL=https://127.0.0.1

# Trading Calendar (si corre en tu máquina)
CALENDAR_BASE_URL=http://localhost:8000

# Scanner
SCANNER_PORT=8001
INPUT_FOLDER=./input
```

### 2. Primer arranque

```batch
iniciar.bat
```

El servidor FastAPI arrancará en `http://localhost:8001`.

### 3. Actualizar código

```batch
actualizar.bat
```

Esto hace `git pull` y `uv sync` para mantener todo sincronizado.

## Estructura del Proyecto

```
trading-scanner/
├── pyproject.toml          # Dependencias con uv
├── .python-version         # Python 3.12
├── .env                    # Credenciales (NO en repo)
├── CLAUDE.md               # Especificación completa del sistema
│
├── src/trading_scanner/
│   ├── config.py           # Settings con Pydantic
│   ├── models.py           # Todos los modelos Pydantic
│   ├── database.py         # Cliente de Turso via HTTP API v2
│   ├── main.py             # FastAPI app
│   │
│   ├── ingest/             # (próximamente)
│   ├── fetchers/           # (próximamente)
│   ├── indicators/         # (próximamente)
│   ├── engine/             # (próximamente)
│   ├── backtest/           # (próximamente)
│   └── optimizer/          # (próximamente)
│
├── input/                  # CSV de ToS (watcheado)
├── backtest_data/          # Cache local de históricos (.parquet)
├── templates/              # Jinja2
├── static/                 # HTMX + CSS
│
└── tests/
    ├── unit/               # Tests unitarios (sin red)
    ├── integration/        # Tests con servicios reales
    └── e2e/                # Flujos completos
```

## Sprint 1: Ingesta CSV + Schwab API + Evaluador

Implementar:

1. ✅ Estructura de proyecto con pyproject.toml
2. ⏳ CSV Watcher (watchdog)
3. ⏳ Schwab REST API client (schwab-py)
4. ⏳ Mercado Data Cache (en memoria)
5. ⏳ Motor de Evaluación (función pura)
6. ⏳ Modelos Pydantic para persistencia
7. ⏳ HTTP API v2 de Turso

## Testing

```bash
# Tests unitarios (sin red, sin archivos)
uv run pytest tests/unit/ -v

# Tests de integración (requieren credenciales reales)
uv run pytest tests/integration/ -v -m integration

# Backtesting completo (lento, manual)
uv run pytest tests/e2e/test_csv_to_result.py -v -m slow
```

## Comandos Útiles

```bash
# Ejecutar app
uv run python -m trading_scanner.main

# Instalar nueva dependencia
uv pip install nombre-libreria

# Actualizar lockfile
uv sync

# Ejecutar tests
uv run pytest tests/unit/ -v
```

## Reglas No Negociables

1. **Sin `pandas` — siempre `polars`** salvo en `pandas-ta` para indicadores
2. **Sin SQLite local — siempre Turso** (libSQL HTTP API v2)
3. **Sin hardcodear umbrales — todo desde `ScanConfig`**
4. **El evaluador es función pura** — sin side effects, testeable
5. **Sin bloquear operaciones por falta de datos** — degradar gracefully
6. **No pushear `.env`, `backtest_data/`, `__pycache__`**
7. **Las credenciales de Schwab NUNCA en el repo**
8. **No reiniciar WebSocket** cuando llega CSV nuevo durante sesión

## Contacto & Documentación

- **Especificación**: Lee [CLAUDE.md](CLAUDE.md)
- **Status**: Ver tabla de sprints en CLAUDE.md
- **Arquitectura**: Diagrama ASCII en CLAUDE.md sección "ARQUITECTURA DEL SISTEMA"
- **Modelos**: Pydantic BaseModel en [src/trading_scanner/models.py](src/trading_scanner/models.py)

---

**Estado del Proyecto**: Sprint 1 — Estructura inicial completada ✓

**Próximos pasos**: Implementar CSV Watcher e integración con Schwab API
