import math

from src.trading_scanner.backtest.metrics import EstrategiaMetrics
from src.trading_scanner.optimizer.fitness import FitnessConfig, calcular_fitness


def _metrics(**overrides) -> EstrategiaMetrics:
    base = dict(
        total_trades=50,
        win_rate=55.0,
        net_profit_r=10.0,
        expectancy_r=0.2,
        profit_factor=1.5,
        avg_win_r=1.0,
        avg_loss_r=-0.5,
        max_drawdown_r=3.0,
    )
    base.update(overrides)
    return EstrategiaMetrics(**base)


def test_cero_trades_da_fitness_minimo():
    metrics = _metrics(total_trades=0)
    assert calcular_fitness(metrics) == -math.inf


def test_mayor_expectancy_da_mayor_fitness():
    config = FitnessConfig()
    peor = calcular_fitness(_metrics(expectancy_r=0.1), config)
    mejor = calcular_fitness(_metrics(expectancy_r=0.5), config)
    assert mejor > peor


def test_mayor_drawdown_penaliza_el_fitness():
    config = FitnessConfig()
    bajo_dd = calcular_fitness(_metrics(max_drawdown_r=1.0), config)
    alto_dd = calcular_fitness(_metrics(max_drawdown_r=10.0), config)
    assert bajo_dd > alto_dd


def test_pocos_trades_penaliza_gradualmente_no_de_golpe():
    # score_base robustamente positivo (expectancy y profit factor superan
    # holgadamente al drawdown) para aislar el efecto de la cantidad de trades.
    config = FitnessConfig(trades_objetivo=30)
    metrics_buena = dict(expectancy_r=0.3, profit_factor=2.0, max_drawdown_r=1.0)
    fitness_5 = calcular_fitness(_metrics(total_trades=5, **metrics_buena), config)
    fitness_15 = calcular_fitness(_metrics(total_trades=15, **metrics_buena), config)
    fitness_30 = calcular_fitness(_metrics(total_trades=30, **metrics_buena), config)
    fitness_60 = calcular_fitness(_metrics(total_trades=60, **metrics_buena), config)

    # Positivo y monótono creciente con más trades, sin un salto discreto:
    # una buena estrategia con pocos trades todavía compite (score > 0),
    # pero gana terreno a medida que hay más evidencia de que es buena.
    assert 0 < fitness_5 < fitness_15 < fitness_30 < fitness_60


def test_estrategia_mala_penaliza_mas_con_mas_trades_no_menos():
    # El factor de confiabilidad escala la confianza en la medición en ambos
    # sentidos: una estrategia con score_base negativo se castiga MÁS (no
    # menos) a medida que hay más trades que confirman que es mala — pocos
    # trades malos todavía podrían ser ruido, muchos trades malos no.
    config = FitnessConfig(trades_objetivo=30)
    metrics_mala = dict(expectancy_r=0.1, profit_factor=0.8, max_drawdown_r=5.0)
    fitness_5 = calcular_fitness(_metrics(total_trades=5, **metrics_mala), config)
    fitness_60 = calcular_fitness(_metrics(total_trades=60, **metrics_mala), config)
    assert fitness_60 < fitness_5 < 0


def test_profit_factor_tope_evita_que_un_outlier_domine():
    config = FitnessConfig(profit_factor_tope=5.0)
    normal = calcular_fitness(_metrics(profit_factor=5.0), config)
    outlier = calcular_fitness(_metrics(profit_factor=500.0), config)
    assert normal == outlier


def test_max_drawdown_tope_evita_que_estrategias_de_alta_frecuencia_lo_dominen():
    """Hallazgo real (2026-08-06): calibrando 3BP/4BP (cientos-miles de
    trades por corrida, a diferencia de los ~15-30 del clasificador de 6
    criterios) max_drawdown_r es una SUMA sobre toda la serie -> crece sin
    límite con más trades y ahoga a expectancy/profit_factor (que sí son
    tasas). Sin el cap, un drawdown de 34 vs uno de 15 seguiría
    diferenciando fitness aunque ambos ya sean "claramente malos" — con el
    cap, ambos empatan en el peor score posible."""
    config = FitnessConfig(max_drawdown_tope=15.0)
    en_el_tope = calcular_fitness(_metrics(max_drawdown_r=15.0), config)
    muy_por_encima = calcular_fitness(_metrics(max_drawdown_r=34.3), config)
    assert en_el_tope == muy_por_encima


def test_max_drawdown_tope_no_afecta_drawdowns_normales_del_clasificador():
    """El default (15.0) es deliberadamente generoso — no debe cambiar el
    comportamiento para el rango de drawdown que ya se observó en el
    clasificador de 6 criterios (hasta ahora, nunca superó ~2R)."""
    config = FitnessConfig()
    bajo_dd = calcular_fitness(_metrics(max_drawdown_r=1.0), config)
    alto_dd = calcular_fitness(_metrics(max_drawdown_r=2.0), config)
    assert bajo_dd > alto_dd  # sigue discriminando normalmente, sin tocar el tope
