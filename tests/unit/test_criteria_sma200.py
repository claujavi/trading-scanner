from src.trading_scanner.engine.criteria import criterio_sma200


def test_criterio_sma200_alcista_da_score_day():
    assert criterio_sma200("ALCISTA") == (1.0, 0.0)


def test_criterio_sma200_bajista_da_score_swing():
    assert criterio_sma200("BAJISTA") == (0.0, 1.0)


def test_criterio_sma200_none_es_no_calculable_sin_fallback():
    """Estructura mixta o datos insuficientes -> None. No hace fallback a
    ningún bit binario (decisión confirmada en docs/spec_criterio_pivotes.md)."""
    assert criterio_sma200(None) is None


def test_criterio_sma200_valor_desconocido_tambien_es_none():
    assert criterio_sma200("ALGO_INESPERADO") is None
