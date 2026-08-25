import asyncio
from datetime import date, datetime

import pytest

from src.trading_scanner.backtest import metrics_3bp
from src.trading_scanner.backtest.metrics_3bp import calcular_metricas_3bp, recolectar_eventos_3bp
from src.trading_scanner.models import Bp34Evento, FuenteDatos, ResultadoBp34, ScanConfig


def _evento(resultado_r: float, tier: str = "confirmado", resultado: ResultadoBp34 = ResultadoBp34.TARGET) -> Bp34Evento:
    return Bp34Evento(
        ticker="AAPL",
        timeframe="5m",
        fecha=date(2026, 1, 2),
        timestamp=datetime(2026, 1, 2, 9, 35),
        fuente=FuenteDatos.HISTORICO,
        tipo="3BP",
        tier=tier,
        entry=10.0,
        stop=9.0,
        target=12.0,
        resultado=resultado,
        resultado_r=resultado_r,
        mfe_r=abs(resultado_r) + 0.1,
        mae_r=-0.05,
        tiempo_en_trade_minutos=10,
        config_snapshot={},
    )


def test_calcular_metricas_win_rate_y_profit_factor():
    eventos = [
        _evento(2.0, tier="confirmado", resultado=ResultadoBp34.TARGET),
        _evento(-1.0, tier="confirmado", resultado=ResultadoBp34.STOP),
        _evento(0.3, tier="sin_confirmar", resultado=ResultadoBp34.SIN_DEFINIR),
        _evento(-1.0, tier="sin_confirmar", resultado=ResultadoBp34.STOP),
    ]

    m = calcular_metricas_3bp(eventos)

    assert m["total_eventos"] == 4
    assert m["total_entradas"] == 4
    assert m["win_rate"] == 50.0  # 2 ganadores de 4
    assert m["win_rate_confirmado"] == 50.0  # 1 de 2 (target gana, stop pierde)
    assert m["win_rate_sin_confirmar"] == 50.0  # 1 de 2 (sin_definir positivo gana, stop pierde)
    assert m["rr_promedio"] == pytest.approx((2.0 - 1.0 + 0.3 - 1.0) / 4)
    assert m["señales_target"] == 1
    assert m["señales_stop"] == 2
    assert m["señales_sin_definir"] == 1


def test_calcular_metricas_lista_vacia_no_rompe():
    m = calcular_metricas_3bp([])
    assert m["total_eventos"] == 0
    assert m["total_entradas"] == 0
    assert m["win_rate"] == 0.0
    assert m["rr_promedio"] == 0.0
    assert m["profit_factor"] == 0.0


def test_calcular_metricas_filtra_eventos_sin_resolver():
    """Defensivo: un evento ABIERTO (resultado_r=None, ej. proveniente de
    vivo) no debe romper ni contarse como entrada resuelta."""
    abierto = Bp34Evento(
        ticker="AAPL", timeframe="5m", fecha=date(2026, 1, 2), timestamp=datetime(2026, 1, 2, 9, 35),
        fuente=FuenteDatos.LIVE, tipo="3BP", tier="confirmado", entry=10.0, stop=9.0, target=12.0,
        resultado=ResultadoBp34.ABIERTO, resultado_r=None, config_snapshot={},
    )
    eventos = [_evento(1.0), abierto]

    m = calcular_metricas_3bp(eventos)
    assert m["total_eventos"] == 2
    assert m["total_entradas"] == 1


def test_recolectar_eventos_ordena_por_timestamp_entre_tickers(monkeypatch):
    """asyncio.gather aplana por ticker (orden de la lista `tickers`, alfabético
    en la práctica), no por fecha real. Sin ordenar por timestamp acá, cualquier
    cálculo que trate la lista como una curva de capital secuencial (ej.
    _max_drawdown_r) recorrería primero todo el historial de un ticker y
    después el del siguiente — una racha perdedora artificial. Ver hallazgo de
    la calibración 2026-08-24 (drawdown inflado a 47R sobre 6923 trades)."""
    eventos_por_ticker = {
        "AAPL": [_evento(1.0).model_copy(update={"ticker": "AAPL", "timestamp": datetime(2026, 3, 1, 9, 35)})],
        "MSFT": [_evento(1.0).model_copy(update={"ticker": "MSFT", "timestamp": datetime(2026, 1, 5, 9, 35)})],
        "ZZZ": [_evento(1.0).model_copy(update={"ticker": "ZZZ", "timestamp": datetime(2026, 2, 15, 9, 35)})],
    }

    async def _caminar_falso(ticker, timeframe, fecha_inicio, fecha_fin, config):
        return eventos_por_ticker[ticker]

    monkeypatch.setattr(metrics_3bp, "caminar_3bp", _caminar_falso)

    eventos = asyncio.run(
        recolectar_eventos_3bp(
            ["AAPL", "MSFT", "ZZZ"], "5m", date(2026, 1, 1), date(2026, 3, 31), ScanConfig()
        )
    )

    assert [e.ticker for e in eventos] == ["MSFT", "ZZZ", "AAPL"]
    assert [e.timestamp for e in eventos] == sorted(e.timestamp for e in eventos)
