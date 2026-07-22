import asyncio
from datetime import date
from pathlib import Path

import pytest

import src.trading_scanner.optimizer.study as study_module
from src.trading_scanner.backtest.simulator import ResultadoSimulacion
from src.trading_scanner.models import ScanConfig
from src.trading_scanner.optimizer.fitness import FitnessConfig


async def _fake_recolectar_resultados_universo_real(universo, config):
    """Simulaciones sintéticas cuya cantidad depende de rr_target, para poder
    ejercitar el loop de trials sin red ni Schwab."""
    n = max(1, int(round(config.rr_target * 10)))
    resultados = []
    for i in range(n):
        r = 1.0 if i % 2 == 0 else -0.5
        resultados.append((None, ResultadoSimulacion(100.0, 100.0, r, "target")))
    return resultados


def _fake_universo_real_csv(input_folder):
    return {date(2026, 1, 5): ["AAA"]}


def test_optimizar_corre_n_trials_y_devuelve_el_mejor(monkeypatch):
    monkeypatch.setattr(
        study_module, "recolectar_resultados_universo_real", _fake_recolectar_resultados_universo_real
    )
    monkeypatch.setattr(study_module, "universo_real_csv", _fake_universo_real_csv)

    fitness_capturados = []
    original_calcular_fitness = study_module.calcular_fitness

    def _spy_calcular_fitness(metrics, config):
        valor = original_calcular_fitness(metrics, config)
        fitness_capturados.append(valor)
        return valor

    monkeypatch.setattr(study_module, "calcular_fitness", _spy_calcular_fitness)

    async def body():
        return await study_module.optimizar(
            ScanConfig(), Path("input"), n_trials=8, fitness_config=FitnessConfig(trades_objetivo=5)
        )

    resultado = asyncio.run(body())

    assert resultado.n_trials == 8
    assert resultado.n_trials_validos == 8
    assert resultado.mejor_metrics.total_trades > 0
    assert resultado.mejor_fitness == max(fitness_capturados)

    n_esperado = max(1, int(round(resultado.mejor_config.rr_target * 10)))
    assert resultado.mejor_metrics.total_trades == n_esperado


def test_optimizar_lanza_value_error_sin_universo(monkeypatch):
    monkeypatch.setattr(study_module, "universo_real_csv", lambda input_folder: {})

    async def body():
        await study_module.optimizar(ScanConfig(), Path("input"), n_trials=1, fitness_config=FitnessConfig())

    with pytest.raises(ValueError):
        asyncio.run(body())
