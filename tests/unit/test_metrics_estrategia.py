from src.trading_scanner.backtest.metrics import calcular_metricas_estrategia
from src.trading_scanner.backtest.simulator import ResultadoSimulacion


def _sim(r: float) -> ResultadoSimulacion:
    return ResultadoSimulacion(precio_entrada=100.0, precio_salida=100.0, resultado_r=r, motivo_salida="target")


def test_sin_trades_no_rompe_y_da_todo_cero():
    metrics = calcular_metricas_estrategia([])
    assert metrics.total_trades == 0
    assert metrics.win_rate == 0.0
    assert metrics.net_profit_r == 0.0
    assert metrics.expectancy_r == 0.0
    assert metrics.profit_factor == 0.0
    assert metrics.avg_win_r == 0.0
    assert metrics.avg_loss_r == 0.0
    assert metrics.max_drawdown_r == 0.0


def test_metricas_con_trades_mixtos():
    simulaciones = [_sim(2.0), _sim(-1.0), _sim(3.0), _sim(-0.5)]
    metrics = calcular_metricas_estrategia(simulaciones)

    assert metrics.total_trades == 4
    assert metrics.win_rate == 50.0
    assert metrics.net_profit_r == 3.5
    assert metrics.expectancy_r == 3.5 / 4
    assert metrics.profit_factor == 5.0 / 1.5
    assert metrics.avg_win_r == (2.0 + 3.0) / 2
    assert metrics.avg_loss_r == (-1.0 + -0.5) / 2


def test_todos_ganadores_profit_factor_es_la_ganancia_total():
    simulaciones = [_sim(1.0), _sim(2.0)]
    metrics = calcular_metricas_estrategia(simulaciones)
    assert metrics.profit_factor == 3.0
    assert metrics.avg_loss_r == 0.0
    assert metrics.max_drawdown_r == 0.0


def test_max_drawdown_detecta_caida_desde_pico():
    # +3, +2 (pico=5), -4 (cae a 1, dd=4), +1 (sube a 2)
    simulaciones = [_sim(3.0), _sim(2.0), _sim(-4.0), _sim(1.0)]
    metrics = calcular_metricas_estrategia(simulaciones)
    assert metrics.max_drawdown_r == 4.0
