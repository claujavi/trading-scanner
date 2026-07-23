"""
cli_precarga.py — precarga histórica del cache de Parquet (backtest_data/)
para un universo de tickers, en varios timeframes, respetando el rate
limit de Schwab.

Por qué existe: pedirle a Schwab muchos tickers x timeframes en poco tiempo
(como hace un backtest o el optimizador corriendo sobre un rango amplio
todavía no cacheado) puede disparar un 429 — ya pasó una vez en Sprint 3
(de ahí el límite de concurrencia en runner.py) y volvió a pasar corriendo
el optimizador con universo curado sobre fechas sin intradía cacheado. Este
comando hace lo mismo (pedir historial vía history_cache.py) pero
deliberadamente lento y secuencial (sin concurrencia), con backoff largo
ante un 429, pensado para dejarlo corriendo horas o días sin supervisión.

Seguro de interrumpir (Ctrl+C) y volver a correr: history_cache.get_history()
ya se salta lo que esté cacheado, así que retoma exactamente donde quedó —
no hay estado propio que mantener.

    uv run trading-scanner-precargar-historico
    uv run trading-scanner-precargar-historico --tickers AAPL,TSLA \
        --fecha-inicio 2024-01-01 --fecha-fin 2026-07-22
"""

import asyncio
from datetime import date, timedelta
from typing import Optional

import typer
from rich.console import Console

from .fetchers import history_cache
from .fetchers.schwab_history import SchwabRateLimitError

app = typer.Typer()
console = Console()

_TIMEFRAMES_DEFAULT = ["d", "4h", "15m", "5m"]


def _parse_tickers(raw: str) -> list[str]:
    separadores = raw.replace(",", "\n").replace(" ", "\n")
    return sorted({t.strip().upper() for t in separadores.splitlines() if t.strip()})


async def _precargar_uno(
    ticker: str,
    timeframe: str,
    fecha_inicio: date,
    fecha_fin: date,
    pausa_base: float,
    max_espera: float,
) -> str:
    """Intenta cachear un ticker/timeframe. Ante un 429 espera con backoff
    exponencial (sin límite de intentos — pensado para correr desatendido
    durante horas/días) y reintenta; cualquier otro error se loguea y se
    sigue con el próximo, sin reintentar (mismo criterio que runner.py)."""
    espera = pausa_base
    while True:
        try:
            await history_cache.get_history(ticker, timeframe, fecha_inicio, fecha_fin)
            return "ok"
        except SchwabRateLimitError:
            espera = min(espera * 2, max_espera)
            console.log(f"[yellow]429 en {ticker} {timeframe} — esperando {espera:.0f}s antes de reintentar[/yellow]")
            await asyncio.sleep(espera)
        except Exception as exc:
            console.log(f"[red]{ticker} {timeframe}: {exc}[/red]")
            return "error"


@app.command()
def run(
    tickers: Optional[str] = typer.Option(
        None,
        help="Tickers separados por coma. Default: los que ya tienen historial diario cacheado.",
    ),
    fecha_inicio: Optional[str] = typer.Option(
        None, help="YYYY-MM-DD. Default: el inicio del rango diario ya cacheado."
    ),
    fecha_fin: Optional[str] = typer.Option(None, help="YYYY-MM-DD. Default: hoy."),
    timeframes: str = typer.Option(
        ",".join(_TIMEFRAMES_DEFAULT), help="Timeframes a precargar, separados por coma."
    ),
    pausa: float = typer.Option(
        1.5, help="Segundos de espera entre cada pedido real a Schwab (no entre los ya cacheados)."
    ),
    max_espera: float = typer.Option(
        600.0, help="Tope del backoff exponencial ante un 429, en segundos."
    ),
) -> None:
    """Precarga Parquet para muchos tickers/timeframes, uno a la vez, con
    pausas entre pedidos reales y backoff largo ante rate limit."""
    lista_tickers = _parse_tickers(tickers) if tickers else history_cache.tickers_cacheados("d")
    if not lista_tickers:
        console.log("[red]No hay tickers para precargar (ni pasados por --tickers ni cacheados).[/red]")
        raise typer.Exit(code=1)

    rango_actual = history_cache.rango_cacheado("d")
    fi = (
        date.fromisoformat(fecha_inicio)
        if fecha_inicio
        else (rango_actual[0] if rango_actual else date.today() - timedelta(days=365))
    )
    ff = date.fromisoformat(fecha_fin) if fecha_fin else date.today()
    lista_timeframes = [t.strip() for t in timeframes.split(",") if t.strip()]

    total = len(lista_tickers) * len(lista_timeframes)
    console.log(
        f"[green]Precarga iniciada: {len(lista_tickers)} tickers x {len(lista_timeframes)} "
        f"timeframes ({fi} a {ff}) = {total} combinaciones[/green]"
    )

    resultados = {"ok": 0, "error": 0}

    async def _correr() -> None:
        i = 0
        for ticker in lista_tickers:
            for timeframe in lista_timeframes:
                i += 1
                ya_estaba = history_cache.esta_cacheado(ticker, timeframe, fi, ff)
                estado = await _precargar_uno(ticker, timeframe, fi, ff, pausa, max_espera)
                resultados[estado] = resultados.get(estado, 0) + 1
                console.log(
                    f"[{i}/{total}] {ticker} {timeframe}: {estado}"
                    + (" (ya estaba)" if ya_estaba else "")
                )
                if not ya_estaba:
                    await asyncio.sleep(pausa)

    asyncio.run(_correr())

    console.log(
        f"[green]Precarga completa: {resultados.get('ok', 0)} ok, "
        f"{resultados.get('error', 0)} con error/sin datos[/green]"
    )


if __name__ == "__main__":
    app()
