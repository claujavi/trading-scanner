"""
cli.py — comando separado para correr el optimizador.

Por regla de CLAUDE.md ("No correr el optimizador en producción — Optuna
consume CPU intensivamente, tiene su propio comando separado"), esto NUNCA se
expone como endpoint de FastAPI. Se invoca manualmente:

    uv run trading-scanner-optimize --n-trials 100
    uv run trading-scanner-optimize --universo curado --tickers AAPL,TSLA,NVDA \
        --fecha-inicio 2024-01-01 --fecha-fin 2026-01-01

Al terminar, muestra la config ganadora y sus métricas objetivas (separadas
del fitness_score, que es solo el criterio de ranking del optimizador) y
pregunta antes de escribir nada en Turso.
"""

import asyncio
from datetime import date
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ..config import settings
from ..database import db
from ..pipeline import get_active_config
from .fitness import FitnessConfig
from .study import construir_backtest_run_final, optimizar
from .universo import universo_curado, universo_real

app = typer.Typer()
console = Console()


def _parse_tickers(raw: str) -> list[str]:
    separadores = raw.replace(",", " ")
    return sorted({t.strip().upper() for t in separadores.split() if t.strip()})


@app.command()
def run(
    n_trials: int = typer.Option(100, help="Cantidad de trials de Optuna a correr."),
    trades_objetivo: int = typer.Option(
        30, help="Cantidad de trades a partir de la cual el fitness deja de penalizar por poca muestra."
    ),
    universo: str = typer.Option(
        "real",
        help=(
            "'real' (default): fiel a los CSV guardados en input/, limitado a esos días. "
            "'curado': lista fija de tickers contra un rango de fechas arbitrario (más volumen "
            "de datos, pero mide algo distinto — ver optimizer/universo.py)."
        ),
    ),
    input_folder: str = typer.Option(
        settings.input_folder, help="Carpeta con los CSV históricos (solo para --universo real)."
    ),
    tickers: Optional[str] = typer.Option(
        None, help="Tickers separados por coma (solo para --universo curado, ej: AAPL,TSLA,NVDA)."
    ),
    fecha_inicio: Optional[str] = typer.Option(
        None, help="YYYY-MM-DD (solo para --universo curado)."
    ),
    fecha_fin: Optional[str] = typer.Option(
        None, help="YYYY-MM-DD (solo para --universo curado)."
    ),
    guardar: bool = typer.Option(
        False, "--guardar/--no-guardar", help="Guardar la config ganadora en Turso sin preguntar."
    ),
) -> None:
    """Corre el optimizador de parámetros contra el universo real o curado."""
    if universo == "curado":
        if not tickers or not fecha_inicio or not fecha_fin:
            console.log(
                "[red]--universo curado requiere --tickers, --fecha-inicio y --fecha-fin[/red]"
            )
            raise typer.Exit(code=1)
        fuente = universo_curado(
            _parse_tickers(tickers), date.fromisoformat(fecha_inicio), date.fromisoformat(fecha_fin)
        )
        console.log(
            f"[yellow]Universo curado: {len(fuente.tickers)} tickers, {fuente.fecha_inicio} a "
            f"{fuente.fecha_fin}. Mide algo distinto al universo real — revalidar después contra "
            f"universo real cuando haya más días de CSV.[/yellow]"
        )
    else:
        fuente = universo_real(Path(input_folder))

    config_base = asyncio.run(get_active_config())
    fitness_config = FitnessConfig(trades_objetivo=trades_objetivo)

    console.log(f"[green]Optimizador iniciado: {n_trials} trials, config base = {config_base.nombre}[/green]")
    resultado = asyncio.run(optimizar(config_base, fuente, n_trials, fitness_config))

    console.print(
        f"\n[bold green]Mejor trial: fitness={resultado.mejor_fitness:.4f} "
        f"({resultado.n_trials_validos}/{resultado.n_trials} trials válidos)[/bold green]\n"
    )

    tabla_metricas = Table(title="Métricas objetivas de la config ganadora (en R)")
    tabla_metricas.add_column("Métrica")
    tabla_metricas.add_column("Valor", justify="right")
    m = resultado.mejor_metrics
    tabla_metricas.add_row("Total trades", str(m.total_trades))
    tabla_metricas.add_row("Win rate", f"{m.win_rate:.1f}%")
    tabla_metricas.add_row("Net profit (R)", f"{m.net_profit_r:.2f}")
    tabla_metricas.add_row("Expectancy (R/trade)", f"{m.expectancy_r:.3f}")
    tabla_metricas.add_row("Profit factor", f"{m.profit_factor:.2f}")
    tabla_metricas.add_row("Avg win (R)", f"{m.avg_win_r:.3f}")
    tabla_metricas.add_row("Avg loss (R)", f"{m.avg_loss_r:.3f}")
    tabla_metricas.add_row("Max drawdown (R)", f"{m.max_drawdown_r:.2f}")
    console.print(tabla_metricas)

    tabla_params = Table(title="Parámetros optimizados")
    tabla_params.add_column("Campo")
    tabla_params.add_column("Valor", justify="right")
    campos_optimizados = [
        "relvol_umbral_day", "relvol_umbral_swing_min", "relvol_umbral_swing_max",
        "atr_pct_umbral_day", "atr_pct_umbral_swing_min", "atr_pct_umbral_swing_max",
        "ivr_umbral_compra", "ivr_umbral_venta", "umbral_decision",
        "rr_target", "stop_atr_multiplicador", "slippage_bps",
    ]
    for campo in campos_optimizados:
        tabla_params.add_row(campo, str(getattr(resultado.mejor_config, campo)))
    console.print(tabla_params)

    if not guardar:
        guardar = typer.confirm("\n¿Guardar la config ganadora como nueva ScanConfig activa?")
    if not guardar:
        console.log("[yellow]Config ganadora no guardada.[/yellow]")
        raise typer.Exit()

    async def _persistir() -> None:
        backtest_run = await construir_backtest_run_final(resultado.mejor_config, fuente)
        await db.insert_scan_config(resultado.mejor_config.model_dump(mode="json"))
        await db.insert_backtest_run(backtest_run.model_dump(mode="json"))

    asyncio.run(_persistir())
    console.log("[green]Config ganadora guardada en Turso (scan_configs + backtest_runs).[/green]")


if __name__ == "__main__":
    app()
