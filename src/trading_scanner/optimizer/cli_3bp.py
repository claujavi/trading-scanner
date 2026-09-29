"""
cli_3bp.py — comando separado para calibrar los parámetros bp34_* de un
timeframe del módulo 3BP/4BP (docs/spec_modulo_3bp_4bp.md) contra el
universo curado ya cacheado en backtest_data/.

Deliberadamente separado de optimizer/cli.py: ese comando calibra los
umbrales/pesos del clasificador de 6 criterios sobre FuenteUniverso.recolectar()
(evaluator + simulator.py), un pipeline distinto al walker vela-por-vela de
walker_3bp.py que usa este módulo. Reusa igual el mismo patrón de resume vía
Optuna storage/study_name (optimizer/study.py::optimizar) para que un run
interrumpido (proceso matado, PC reiniciada, corte de luz) se retome exacto
donde quedó.

    uv run trading-scanner-optimize-3bp --timeframe 15m --n-trials 50 \
        --study-name 3bp_15m_universo_completo

Sin --tickers, usa todos los cacheados para el timeframe pedido
(history_cache.tickers_cacheados). Sin --fecha-inicio/--fecha-fin, usa el
rango cacheado completo — walker_3bp.py ya recorta internamente a
history_cache.FECHA_INICIO_DEFAULT (Schwab no tiene más profundidad
intradía real, ver CLAUDE.md), así que pedir una fecha_inicio más vieja no
cuesta nada.
"""

import asyncio
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import optuna
import typer
from rich.table import Table

from ..config import settings
from ..fetchers import history_cache
from ..logging_setup import console
from ..models import ScanConfig
from ..pipeline import get_active_config
from ..backtest.metrics import calcular_metricas_estrategia
from ..backtest.metrics_3bp import recolectar_eventos_3bp
from .fitness import FitnessConfig, calcular_fitness

app = typer.Typer()

optuna.logging.set_verbosity(optuna.logging.WARNING)

_TIMEFRAMES_3BP = ("5m", "15m")


def ultimo_dia_mes_cerrado(hoy: date) -> date:
    """Último día del mes anterior a `hoy`. history_cache.get_history() cae a
    Schwab en vivo si falta el parquet de cualquier mes del rango pedido, y el
    mes en curso nunca está cerrado en cache (pipeline._actualizar_cache_historico
    solo lo refresca para los tickers del CSV de ToS del día, no para los
    ~400 de la calibración) — acotar fecha_fin acá mantiene la corrida 100% local."""
    return hoy.replace(day=1) - timedelta(days=1)


def _parse_tickers(raw: str) -> list[str]:
    separadores = raw.replace(",", " ")
    return sorted({t.strip().upper() for t in separadores.split() if t.strip()})


def _sugerir_config_3bp(trial: optuna.Trial, config_base: ScanConfig, timeframe: str) -> ScanConfig:
    """Samplea los 5 parámetros bp34_* del timeframe pedido (spec, sección
    1: WRB, tolerancia, N de invalidación, target R son por timeframe; el
    umbral de volumen es compartido, ver models.py). Nunca toca los del otro
    timeframe ni ningún campo del clasificador de 6 criterios."""
    overrides = {
        f"bp34_wrb_multiplicador_{timeframe}": trial.suggest_float("wrb_multiplicador", 1.0, 4.0),
        f"bp34_tolerancia_pct_{timeframe}": trial.suggest_float("tolerancia_pct", 0.05, 0.5),
        f"bp34_n_invalidacion_{timeframe}": trial.suggest_int("n_invalidacion", 3, 30),
        f"bp34_target_r_{timeframe}": trial.suggest_float("target_r", 1.0, 5.0),
        f"bp34_ventana_inicio_barras_{timeframe}": trial.suggest_int("ventana_inicio_barras", 2, 8),
        "bp34_volumen_confirmado_mult": trial.suggest_float("volumen_confirmado_mult", 1.2, 4.0),
    }
    return config_base.model_copy(update=overrides)


async def _calibrar(
    timeframe: str,
    tickers: list[str],
    fecha_inicio: date,
    fecha_fin: date,
    n_trials: int,
    fitness_config: FitnessConfig,
    storage: Optional[str],
    study_name: Optional[str],
    overrides_config: Optional[dict] = None,
) -> tuple[optuna.Study, ScanConfig]:
    config_base = await get_active_config()
    if overrides_config:
        config_base = config_base.model_copy(update=overrides_config)
    study = optuna.create_study(
        direction="maximize", storage=storage, study_name=study_name, load_if_exists=True,
    )
    ya_hechos = sum(1 for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE)
    if ya_hechos:
        console.log(f"[cyan]Retomando study existente: {ya_hechos} trials completos[/cyan]")

    for i in range(ya_hechos, n_trials):
        trial = study.ask()
        config = _sugerir_config_3bp(trial, config_base, timeframe)

        eventos = await recolectar_eventos_3bp(tickers, timeframe, fecha_inicio, fecha_fin, config)
        resueltos = [e for e in eventos if e.resultado_r is not None]
        metrics = calcular_metricas_estrategia(resueltos)
        fitness = calcular_fitness(metrics, fitness_config)

        trial.set_user_attr("metrics", metrics.__dict__)
        study.tell(trial, fitness)

        console.log(
            f"[cyan]Trial {i + 1}/{n_trials}[/cyan] fitness={fitness:.4f} "
            f"trades={metrics.total_trades} expectancy_r={metrics.expectancy_r:.3f} "
            f"drawdown_r={metrics.max_drawdown_r:.2f}"
        )

    return study, config_base


@app.command()
def run(
    timeframe: str = typer.Option("15m", help="'5m' o '15m' — perfiles independientes, nunca mezclados."),
    n_trials: int = typer.Option(50, help="Cantidad de trials de Optuna a correr."),
    trades_objetivo: int = typer.Option(
        30, help="Cantidad de trades a partir de la cual el fitness deja de penalizar por poca muestra."
    ),
    peso_drawdown: float = typer.Option(
        0.0,
        help=(
            "Peso del max_drawdown_r en el fitness. Default 0 (a diferencia de "
            "optimizer/cli.py): el walker de 3BP no respeta posiciones_simultaneas_max ni "
            "trackea capital, así que la curva de R acumulada no representa ninguna cuenta "
            "real operable — max_drawdown_r queda solo como dato informativo en la tabla "
            "final, no como criterio de ranking. Subirlo de 0 no arregla eso, ver "
            "fitness.py::FitnessConfig.peso_drawdown."
        ),
    ),
    tickers: Optional[str] = typer.Option(
        None, help="Tickers separados por coma. Sin esto: todos los cacheados para --timeframe."
    ),
    fecha_inicio: Optional[str] = typer.Option(None, help="YYYY-MM-DD. Sin esto: inicio del rango cacheado."),
    fecha_fin: Optional[str] = typer.Option(None, help="YYYY-MM-DD. Sin esto: fin del rango cacheado."),
    slippage_bps: Optional[float] = typer.Option(
        None,
        help=(
            "Slippage por lado en bps para el walker (entrada, stop, target, cierre). Sin esto usa el "
            "de la config activa. El walker antes lo ignoraba: recomendable >= 5 para 5m."
        ),
    ),
    stop_min_pct: Optional[float] = typer.Option(
        None,
        help=(
            "Distancia mínima entrada-stop en % del precio; descarta entradas con stop más corto "
            "(bp34_stop_min_pct). Sin esto usa el de la config activa (0 = sin mínimo)."
        ),
    ),
    solo_confirmado: bool = typer.Option(
        False,
        "--solo-confirmado/--sin-filtrar-tier",
        help=(
            "Descarta entradas con tier='sin_confirmar' (bp34_solo_tier_confirmado). Ver "
            "docs/resumen_calibracion_3bp_2026-09.md Ronda 5: mejora retorno y drawdown a la vez "
            "en 15m, evidencia mixta en 5m."
        ),
    ),
    sesion_regular: bool = typer.Option(
        True,
        "--sesion-regular/--todas-las-horas",
        help=(
            "Solo se aceptan entradas 9:30-16:00 NY (default); el detector igual se alimenta desde las "
            "4:00 (contexto de pre-market). --todas-las-horas reproduce el comportamiento anterior, con "
            "60% de entradas en pre-market/madrugada (backtest de 2026-09-25, no operables)."
        ),
    ),
    ventana_entrada_min: int = typer.Option(
        90,
        help=(
            "Minutos desde las 9:30 NY durante los cuales se aceptan entradas nuevas (90 = hasta las "
            "11:00; 0 = toda la sesión). Requiere --sesion-regular."
        ),
    ),
    study_name: Optional[str] = typer.Option(
        None,
        help=(
            "Nombre del study de Optuna a persistir en optimizer_state/optuna.db3. Si se pasa, cada "
            "trial se guarda en SQLite a medida que corre y un run interrumpido se retoma exacto "
            "donde quedó volviendo a correr con el mismo nombre."
        ),
    ),
) -> None:
    """Calibra los bp34_* de un timeframe del módulo 3BP/4BP (paso pendiente de
    docs/spec_modulo_3bp_4bp.md, sección 8) — corrida separada del optimizador
    de 6 criterios, nunca mezclada (mismo criterio que ya sigue todo el módulo)."""
    if timeframe not in _TIMEFRAMES_3BP:
        console.log(f"[red]--timeframe debe ser uno de {_TIMEFRAMES_3BP}[/red]")
        raise typer.Exit(code=1)

    lista_tickers = _parse_tickers(tickers) if tickers else history_cache.tickers_cacheados(timeframe)
    if not lista_tickers:
        console.log(f"[red]Sin tickers cacheados para {timeframe} — correr cli_precarga primero.[/red]")
        raise typer.Exit(code=1)

    if fecha_inicio and fecha_fin:
        d_inicio, d_fin = date.fromisoformat(fecha_inicio), date.fromisoformat(fecha_fin)
    else:
        rango = history_cache.rango_cacheado(timeframe)
        if rango is None:
            console.log(f"[red]Sin rango cacheado para {timeframe} y no se pasó --fecha-inicio/--fecha-fin.[/red]")
            raise typer.Exit(code=1)
        d_inicio, d_fin = rango

    tope = ultimo_dia_mes_cerrado(date.today())
    if d_fin > tope:
        console.log(
            f"[yellow]fecha_fin {d_fin} cae en el mes en curso — se acota a {tope} "
            f"(último mes cerrado) para no pegarle a Schwab en vivo.[/yellow]"
        )
        d_fin = tope
    if d_inicio > d_fin:
        console.log(f"[red]Rango vacío tras acotar al último mes cerrado ({d_inicio} > {d_fin}).[/red]")
        raise typer.Exit(code=1)

    storage = None
    if study_name:
        settings.optimizer_state_path.mkdir(parents=True, exist_ok=True)
        storage = f"sqlite:///{settings.optimizer_state_path / 'optuna.db3'}"

    console.log(
        f"[green]Calibración 3BP/{timeframe} iniciada: {len(lista_tickers)} tickers, "
        f"{d_inicio} a {d_fin}, {n_trials} trials, study={study_name or '(in-memory)'}[/green]"
    )

    overrides_config = {}
    if slippage_bps is not None:
        overrides_config["slippage_bps"] = slippage_bps
    if stop_min_pct is not None:
        overrides_config["bp34_stop_min_pct"] = stop_min_pct
    if ventana_entrada_min > 0 and not sesion_regular:
        console.log("[red]--ventana-entrada-min requiere --sesion-regular.[/red]")
        raise typer.Exit(code=1)
    overrides_config["bp34_entradas_solo_sesion_regular"] = sesion_regular
    overrides_config["bp34_ventana_entrada_minutos"] = ventana_entrada_min
    overrides_config["bp34_solo_tier_confirmado"] = solo_confirmado
    if overrides_config:
        console.log(f"[cyan]Overrides sobre la config activa: {overrides_config}[/cyan]")

    fitness_config = FitnessConfig(trades_objetivo=trades_objetivo, peso_drawdown=peso_drawdown)
    study, _ = asyncio.run(
        _calibrar(
            timeframe, lista_tickers, d_inicio, d_fin, n_trials, fitness_config, storage, study_name,
            overrides_config,
        )
    )

    completos = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
    if not completos:
        console.log("[red]Ningún trial completó — nada para mostrar.[/red]")
        raise typer.Exit(code=1)

    # Algún trial completo puede no tener el user_attr "metrics" persistido
    # (ej. proceso interrumpido justo entre study.tell() y set_user_attr()
    # en una corrida anterior) — study.best_trial no filtra por eso, así que
    # hay que buscar el mejor trial que sí tenga métricas guardadas.
    con_metricas = [t for t in completos if "metrics" in t.user_attrs]
    if not con_metricas:
        console.log("[red]Ningún trial completo tiene métricas guardadas — nada para mostrar.[/red]")
        raise typer.Exit(code=1)
    mejor = max(con_metricas, key=lambda t: t.value)
    if mejor.number != study.best_trial.number:
        console.log(
            f"[yellow]Aviso: el trial de mejor fitness (#{study.best_trial.number}, "
            f"fitness={study.best_trial.value:.4f}) no tiene métricas guardadas — "
            f"mostrando el mejor CON métricas (#{mejor.number}) en su lugar.[/yellow]"
        )
    console.print(f"\n[bold green]Mejor trial: fitness={mejor.value:.4f} ({len(completos)}/{n_trials} válidos)[/bold green]\n")

    m = mejor.user_attrs["metrics"]
    tabla_metricas = Table(title=f"Métricas objetivas — mejor trial (3BP/{timeframe}, en R)")
    tabla_metricas.add_column("Métrica")
    tabla_metricas.add_column("Valor", justify="right")
    tabla_metricas.add_row("Total trades", str(m["total_trades"]))
    tabla_metricas.add_row("Win rate", f"{m['win_rate']:.1f}%")
    tabla_metricas.add_row("Net profit (R)", f"{m['net_profit_r']:.2f}")
    tabla_metricas.add_row("Expectancy (R/trade)", f"{m['expectancy_r']:.3f}")
    tabla_metricas.add_row("Profit factor", f"{m['profit_factor']:.2f}")
    tabla_metricas.add_row("Avg win (R)", f"{m['avg_win_r']:.3f}")
    tabla_metricas.add_row("Avg loss (R)", f"{m['avg_loss_r']:.3f}")
    tabla_metricas.add_row("Max drawdown (R)", f"{m['max_drawdown_r']:.2f}")
    console.print(tabla_metricas)

    tabla_params = Table(title="Parámetros bp34_* ganadores")
    tabla_params.add_column("Campo")
    tabla_params.add_column("Valor", justify="right")
    for nombre, valor in mejor.params.items():
        tabla_params.add_row(nombre, str(valor))
    console.print(tabla_params)

    console.log(
        "[yellow]No se persiste automáticamente — bp34_* siguen siendo campos de ScanConfig, "
        "aplicar a mano en /config si se decide adoptar esta calibración.[/yellow]"
    )


if __name__ == "__main__":
    app()
