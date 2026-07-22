import asyncio
from datetime import date, datetime

import pytest

import src.trading_scanner.optimizer.study as study_module
from src.trading_scanner.backtest.simulator import ResultadoSimulacion
from src.trading_scanner.models import Clasificacion, FuenteDatos, ScanConfig, ScanResult
from src.trading_scanner.optimizer.fitness import FitnessConfig
from src.trading_scanner.optimizer.universo import FuenteUniverso


def _fake_scan_result() -> ScanResult:
    return ScanResult(
        ticker="AAA",
        fecha=date(2026, 1, 5),
        timestamp=datetime(2026, 1, 5, 14, 0),
        fuente=FuenteDatos.HISTORICO,
        config_snapshot={},
        precio=10.0,
        variacion_diaria_pct=5.0,
        relvol=3.0,
        atr_pct=3.0,
        volumen_actual=1_000_000,
        clasificacion=Clasificacion.DAY,
    )


def _fuente_fake() -> FuenteUniverso:
    """Simulaciones sintéticas cuya cantidad depende de rr_target, para poder
    ejercitar el loop de trials sin red ni Schwab."""

    async def _recolectar(config: ScanConfig):
        n = max(1, int(round(config.rr_target * 10)))
        resultados = []
        for i in range(n):
            r = 1.0 if i % 2 == 0 else -0.5
            resultados.append((_fake_scan_result(), ResultadoSimulacion(100.0, 100.0, r, "target")))
        return resultados

    return FuenteUniverso(
        tickers=["AAA"], fecha_inicio=date(2026, 1, 5), fecha_fin=date(2026, 1, 5), recolectar=_recolectar
    )


def test_optimizar_corre_n_trials_y_devuelve_el_mejor(monkeypatch):
    fuente = _fuente_fake()

    fitness_capturados = []
    original_calcular_fitness = study_module.calcular_fitness

    def _spy_calcular_fitness(metrics, config):
        valor = original_calcular_fitness(metrics, config)
        fitness_capturados.append(valor)
        return valor

    monkeypatch.setattr(study_module, "calcular_fitness", _spy_calcular_fitness)

    async def body():
        return await study_module.optimizar(
            ScanConfig(), fuente, n_trials=8, fitness_config=FitnessConfig(trades_objetivo=5)
        )

    resultado = asyncio.run(body())

    assert resultado.n_trials == 8
    assert resultado.n_trials_validos == 8
    assert resultado.mejor_metrics.total_trades > 0
    assert resultado.mejor_fitness == max(fitness_capturados)

    n_esperado = max(1, int(round(resultado.mejor_config.rr_target * 10)))
    assert resultado.mejor_metrics.total_trades == n_esperado


def test_construir_backtest_run_final_usa_la_fuente_dada():
    fuente = _fuente_fake()

    async def body():
        return await study_module.construir_backtest_run_final(ScanConfig(), fuente)

    backtest_run = asyncio.run(body())

    assert backtest_run.tickers == ["AAA"]
    assert backtest_run.fecha_inicio == date(2026, 1, 5)
    assert backtest_run.fecha_fin == date(2026, 1, 5)
    assert backtest_run.total_operadas > 0
