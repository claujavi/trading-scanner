"""
Capa de acceso a la base de datos Turso via HTTP API v2.

Arquitectura idéntica a trading-calendar:
- Conexión via httpx async
- Funciones _execute() para queries individuales
- Funciones _batch() para múltiples queries
- Pydantic BaseModel puro — sin ORM
- libSQL HTTP API v2 directamente
"""

import json
from datetime import datetime
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from .config import settings


class TursoClient:
    """Cliente de Turso via HTTP API v2."""

    def __init__(self):
        self.base_url = settings.turso_database_url.replace("libsql://", "https://")
        self.auth_token = settings.turso_auth_token
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

    async def _execute(self, sql: str, params: Optional[list[Any]] = None) -> list[dict]:
        """Ejecuta una query individual y retorna los resultados.

        Args:
            sql: Instrucción SQL
            params: Parámetros posicionales para la query

        Returns:
            Lista de dicts con los resultados
        """
        async with httpx.AsyncClient() as client:
            payload = {"statements": [{"sql": sql, "args": params or []}]}
            resp = await client.post(
                f"{self.base_url}/v2/turso/execute",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            # Parsear la respuesta de Turso v2
            if "results" in data and len(data["results"]) > 0:
                result = data["results"][0]
                if "rows" in result:
                    return [dict(zip([col["name"] for col in result["columns"]], row))
                            for row in result["rows"]]
            return []

    async def _batch(self, statements: list[tuple[str, Optional[list]]]) -> list[list[dict]]:
        """Ejecuta múltiples queries en un batch.

        Args:
            statements: Lista de (sql, params) tuples

        Returns:
            Lista de listas de dicts, uno por query
        """
        async with httpx.AsyncClient() as client:
            payload = {
                "statements": [
                    {"sql": sql, "args": params or []} for sql, params in statements
                ]
            }
            resp = await client.post(
                f"{self.base_url}/v2/turso/execute",
                headers=self.headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            # Parsear múltiples resultados
            results = []
            if "results" in data:
                for result in data["results"]:
                    if "rows" in result:
                        rows = [dict(zip([col["name"] for col in result["columns"]], row))
                                for row in result["rows"]]
                    else:
                        rows = []
                    results.append(rows)
            return results

    async def initialize_schema(self) -> None:
        """Crea las tablas si no existen."""
        statements = [
            (self.DDL_SCAN_RESULTS, None),
            (self.DDL_SCAN_CONFIGS, None),
            (self.DDL_BACKTEST_RUNS, None),
            (self.DDL_HISTORY_CACHE_META, None),
        ]
        await self._batch(statements)

    # ────────────────────────────────────────────────────────────────────────
    # SCAN RESULTS
    # ────────────────────────────────────────────────────────────────────────

    async def insert_scan_result(self, result: "ScanResultRow") -> int:
        """Inserta un resultado de scan. Retorna el ID."""
        sql = """
        INSERT INTO scan_results (
            ticker, fecha, timestamp, fuente, config_snapshot,
            config_version, evaluator_version, vix_apertura,
            spy_sobre_sma200, futuros_es_gap_pct, calendar_disponible,
            precio, variacion_diaria_pct, relvol, atr_pct, volumen_actual,
            sobre_sma200, sobre_ema50, cruce_ema_921_5m, cruce_ema_921_15m,
            cruce_ema_921_4h, cruce_ema_921_d, rsi_14_5m, rsi_14_d,
            macd_cruce_alcista_15m, macd_cruce_alcista_d, ivr,
            ivr_señal_day, ivr_señal_swing, warning_calendar, earnings_24h,
            evento_macro_24h, filing_8k_24h, upgrade_downgrade_24h,
            catalizador_detectado, score_day, score_swing, score_max_posible,
            clasificacion, confianza, criterios_incompletos, stop_loss_sugerido,
            target_sugerido, rr_calculado, created_at, updated_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
        """
        params = result.to_list()
        await self._execute(sql, params)
        # Retornar el último ID insertado
        rows = await self._execute("SELECT last_insert_rowid() as id")
        return rows[0]["id"] if rows else 0

    async def get_scan_results_by_date(self, fecha: str) -> list[dict]:
        """Obtiene todos los resultados de un día."""
        sql = "SELECT * FROM scan_results WHERE fecha = ? ORDER BY timestamp DESC"
        return await self._execute(sql, [fecha])

    async def get_latest_scan_results(self, limit: int = 100) -> list[dict]:
        """Obtiene los resultados más recientes."""
        sql = "SELECT * FROM scan_results ORDER BY timestamp DESC LIMIT ?"
        return await self._execute(sql, [limit])

    # ────────────────────────────────────────────────────────────────────────
    # SCAN CONFIGS
    # ────────────────────────────────────────────────────────────────────────

    async def insert_scan_config(self, config: dict) -> int:
        """Inserta una configuración. Retorna el ID."""
        sql = """
        INSERT INTO scan_configs (
            nombre, descripcion, config_snapshot, version, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """
        params = [
            config.get("nombre", "default"),
            config.get("descripcion", ""),
            json.dumps(config),
            "1.0.0",
            datetime.utcnow().isoformat(),
        ]
        await self._execute(sql, params)
        rows = await self._execute("SELECT last_insert_rowid() as id")
        return rows[0]["id"] if rows else 0

    async def get_scan_config(self, config_id: int) -> Optional[dict]:
        """Obtiene una configuración por ID."""
        sql = "SELECT * FROM scan_configs WHERE id = ?"
        rows = await self._execute(sql, [config_id])
        return rows[0] if rows else None

    async def get_latest_scan_config(self) -> Optional[dict]:
        """Obtiene la configuración más reciente."""
        sql = "SELECT * FROM scan_configs ORDER BY created_at DESC LIMIT 1"
        rows = await self._execute(sql)
        return rows[0] if rows else None

    # ────────────────────────────────────────────────────────────────────────
    # BACKTEST RUNS
    # ────────────────────────────────────────────────────────────────────────

    async def insert_backtest_run(self, backtest: dict) -> int:
        """Inserta un resultado de backtest. Retorna el ID."""
        sql = """
        INSERT INTO backtest_runs (
            config_snapshot, config_nombre, fecha_inicio, fecha_fin,
            tickers, total_señales, total_operadas, win_rate_day,
            win_rate_swing, rr_promedio_real, rr_promedio_day,
            rr_promedio_swing, profit_factor, max_drawdown_pct,
            sharpe_ratio, señales_day, señales_swing, señales_ambiguo,
            señales_descartadas, señales_green, señales_yellow,
            señales_red, created_at
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """
        params = [
            json.dumps(backtest.get("config_snapshot", {})),
            backtest.get("config_nombre", "default"),
            backtest.get("fecha_inicio"),
            backtest.get("fecha_fin"),
            json.dumps(backtest.get("tickers", [])),
            backtest.get("total_señales", 0),
            backtest.get("total_operadas", 0),
            backtest.get("win_rate_day", 0.0),
            backtest.get("win_rate_swing", 0.0),
            backtest.get("rr_promedio_real", 0.0),
            backtest.get("rr_promedio_day", 0.0),
            backtest.get("rr_promedio_swing", 0.0),
            backtest.get("profit_factor", 0.0),
            backtest.get("max_drawdown_pct", 0.0),
            backtest.get("sharpe_ratio"),
            backtest.get("señales_day", 0),
            backtest.get("señales_swing", 0),
            backtest.get("señales_ambiguo", 0),
            backtest.get("señales_descartadas", 0),
            backtest.get("señales_green", 0),
            backtest.get("señales_yellow", 0),
            backtest.get("señales_red", 0),
            datetime.utcnow().isoformat(),
        ]
        await self._execute(sql, params)
        rows = await self._execute("SELECT last_insert_rowid() as id")
        return rows[0]["id"] if rows else 0

    async def get_backtest_run(self, backtest_id: int) -> Optional[dict]:
        """Obtiene un resultado de backtest por ID."""
        sql = "SELECT * FROM backtest_runs WHERE id = ?"
        rows = await self._execute(sql, [backtest_id])
        return rows[0] if rows else None

    async def get_latest_backtest_runs(self, limit: int = 10) -> list[dict]:
        """Obtiene los backtests más recientes."""
        sql = "SELECT * FROM backtest_runs ORDER BY created_at DESC LIMIT ?"
        return await self._execute(sql, [limit])

    # ────────────────────────────────────────────────────────────────────────
    # HISTORY CACHE META
    # ────────────────────────────────────────────────────────────────────────

    async def upsert_history_cache_meta(
        self, ticker: str, timeframe: str, fecha_inicio: str, fecha_fin: str,
        archivo: str
    ) -> None:
        """Registra o actualiza metadatos de un archivo cacheado."""
        sql = """
        INSERT INTO history_cache_meta (
            ticker, timeframe, fecha_inicio, fecha_fin, archivo, descargado_en
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, timeframe) DO UPDATE SET
            fecha_inicio=excluded.fecha_inicio,
            fecha_fin=excluded.fecha_fin,
            archivo=excluded.archivo,
            descargado_en=excluded.descargado_en
        """
        params = [
            ticker,
            timeframe,
            fecha_inicio,
            fecha_fin,
            archivo,
            datetime.utcnow().isoformat(),
        ]
        await self._execute(sql, params)

    async def get_history_cache_meta(self, ticker: str, timeframe: str) -> Optional[dict]:
        """Obtiene metadatos del cache para un ticker/timeframe."""
        sql = """
        SELECT * FROM history_cache_meta
        WHERE ticker = ? AND timeframe = ?
        """
        rows = await self._execute(sql, [ticker, timeframe])
        return rows[0] if rows else None

    # ────────────────────────────────────────────────────────────────────────
    # DDL - SCHEMAS
    # ────────────────────────────────────────────────────────────────────────

    DDL_SCAN_RESULTS = """
    CREATE TABLE IF NOT EXISTS scan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        fecha TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        fuente TEXT NOT NULL,
        config_snapshot TEXT NOT NULL,
        config_version TEXT DEFAULT '1.0.0',
        evaluator_version TEXT DEFAULT '1.0.0',
        vix_apertura REAL,
        spy_sobre_sma200 BOOLEAN,
        futuros_es_gap_pct REAL,
        calendar_disponible BOOLEAN DEFAULT 1,
        precio REAL NOT NULL,
        variacion_diaria_pct REAL NOT NULL,
        relvol REAL NOT NULL,
        atr_pct REAL NOT NULL,
        volumen_actual INTEGER NOT NULL,
        sobre_sma200 BOOLEAN,
        sobre_ema50 BOOLEAN,
        cruce_ema_921_5m BOOLEAN,
        cruce_ema_921_15m BOOLEAN,
        cruce_ema_921_4h BOOLEAN,
        cruce_ema_921_d BOOLEAN,
        rsi_14_5m REAL,
        rsi_14_d REAL,
        macd_cruce_alcista_15m BOOLEAN,
        macd_cruce_alcista_d BOOLEAN,
        ivr REAL,
        ivr_señal_day BOOLEAN,
        ivr_señal_swing BOOLEAN,
        warning_calendar TEXT,
        earnings_24h BOOLEAN DEFAULT 0,
        evento_macro_24h BOOLEAN DEFAULT 0,
        filing_8k_24h BOOLEAN DEFAULT 0,
        upgrade_downgrade_24h BOOLEAN DEFAULT 0,
        catalizador_detectado BOOLEAN DEFAULT 0,
        score_day REAL DEFAULT 0.0,
        score_swing REAL DEFAULT 0.0,
        score_max_posible REAL DEFAULT 0.0,
        clasificacion TEXT DEFAULT 'DESCARTAR',
        confianza REAL DEFAULT 0.0,
        criterios_incompletos TEXT DEFAULT '[]',
        stop_loss_sugerido REAL,
        target_sugerido REAL,
        rr_calculado REAL,
        operado BOOLEAN,
        precio_entrada REAL,
        precio_salida REAL,
        resultado_r REAL,
        resultado_usd REAL,
        direccion_correcta BOOLEAN,
        notas TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """

    DDL_SCAN_CONFIGS = """
    CREATE TABLE IF NOT EXISTS scan_configs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        descripcion TEXT,
        config_snapshot TEXT NOT NULL,
        version TEXT DEFAULT '1.0.0',
        created_at TEXT NOT NULL
    )
    """

    DDL_BACKTEST_RUNS = """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        config_snapshot TEXT NOT NULL,
        config_nombre TEXT NOT NULL,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        tickers TEXT NOT NULL,
        total_señales INTEGER DEFAULT 0,
        total_operadas INTEGER DEFAULT 0,
        win_rate_day REAL DEFAULT 0.0,
        win_rate_swing REAL DEFAULT 0.0,
        rr_promedio_real REAL DEFAULT 0.0,
        rr_promedio_day REAL DEFAULT 0.0,
        rr_promedio_swing REAL DEFAULT 0.0,
        profit_factor REAL DEFAULT 0.0,
        max_drawdown_pct REAL DEFAULT 0.0,
        sharpe_ratio REAL,
        señales_day INTEGER DEFAULT 0,
        señales_swing INTEGER DEFAULT 0,
        señales_ambiguo INTEGER DEFAULT 0,
        señales_descartadas INTEGER DEFAULT 0,
        señales_green INTEGER DEFAULT 0,
        señales_yellow INTEGER DEFAULT 0,
        señales_red INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """

    DDL_HISTORY_CACHE_META = """
    CREATE TABLE IF NOT EXISTS history_cache_meta (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticker TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        archivo TEXT NOT NULL,
        descargado_en TEXT NOT NULL,
        UNIQUE(ticker, timeframe)
    )
    """


# Instancia singleton
db = TursoClient()
