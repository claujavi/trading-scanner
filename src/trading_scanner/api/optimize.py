"""
Endpoints del optimizador de parámetros.

GET  /optimize          → formulario (n_trials, trades_objetivo) + progreso
                           de un run en curso, o el resultado del último run
POST /optimize/run       → dispara el optimizador en background
                           (asyncio.create_task) — nunca bloquea el request.
                           Bloqueado SIN excepción entre 8:30–16:30 hora de
                           Nueva York (ver fetchers/schwab_client.py::
                           en_ventana_bloqueo_optimizador — ventana propia,
                           distinta de en_horario_habil que usa el chequeo
                           de conexión Schwab): Optuna corre docenas de
                           backtests completos y compite por CPU con el
                           scanner en vivo, que puede estar activo.
GET  /optimize/status    → partial HTMX con el progreso actual (polling)
POST /optimize/guardar   → persiste la config ganadora del último run
                           (scan_configs + backtest_runs), reemplaza al
                           typer.confirm() del CLI para el mismo flujo.
"""

import asyncio
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ..config import settings
from ..database import db
from ..fetchers.schwab_client import en_ventana_bloqueo_optimizador, estado_conexion
from ..optimizer import state as optimizer_state
from ..optimizer.fitness import FitnessConfig
from ..optimizer.study import construir_backtest_run_final, optimizar
from ..pipeline import get_active_config

router = APIRouter(prefix="/optimize", tags=["Optimizer"])

_INPUT_FOLDER = Path(settings.input_folder)


async def _base_context() -> dict:
    return {
        "mock_schwab": settings.mock_schwab,
        "schwab_estado": await estado_conexion(),
        "optimizador_bloqueado": await en_ventana_bloqueo_optimizador(),
    }


@router.get("", response_class=HTMLResponse)
async def get_optimize_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="optimize.html",
        context={
            "estado": optimizer_state.get_estado(),
            "error_bloqueo": None,
            **await _base_context(),
        },
    )


async def _correr_en_background(n_trials: int, trades_objetivo: int) -> None:
    estado = optimizer_state.get_estado()

    def _on_trial(trial_num: int, fitness: float, metrics) -> None:
        estado.trial_actual = trial_num
        if estado.mejor_fitness is None or fitness > estado.mejor_fitness:
            estado.mejor_fitness = fitness
            estado.mejor_metrics = metrics

    try:
        config_base = await get_active_config()
        fitness_config = FitnessConfig(trades_objetivo=trades_objetivo)
        resultado = await optimizar(
            config_base,
            _INPUT_FOLDER,
            n_trials,
            fitness_config,
            on_trial=_on_trial,
        )
        estado.resultado_final = resultado
    except Exception as exc:
        estado.error = str(exc)
    finally:
        estado.corriendo = False


@router.post("/run")
async def run_optimizer(
    request: Request,
    n_trials: int = Form(50),
    trades_objetivo: int = Form(30),
):
    if await en_ventana_bloqueo_optimizador():
        templates = request.app.state.templates
        return templates.TemplateResponse(
            request=request,
            name="optimize.html",
            context={
                "estado": optimizer_state.get_estado(),
                "error_bloqueo": (
                    "El optimizador está bloqueado ahora — compite por CPU con el scanner en vivo. "
                    "Probá de nuevo fuera de 8:30–16:30 hora de Nueva York, lunes a viernes."
                ),
                **await _base_context(),
            },
            status_code=409,
        )

    optimizer_state.reset_estado(n_trials)
    asyncio.create_task(_correr_en_background(n_trials, trades_objetivo))
    return RedirectResponse("/optimize", status_code=303)


@router.get("/status", response_class=HTMLResponse)
async def get_status_partial(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="partials/optimize_status.html",
        context={"estado": optimizer_state.get_estado()},
    )


@router.post("/guardar")
async def guardar_config_ganadora(request: Request):
    estado = optimizer_state.get_estado()
    if estado.resultado_final is None:
        return RedirectResponse("/optimize", status_code=303)

    backtest_run = await construir_backtest_run_final(
        estado.resultado_final.mejor_config, _INPUT_FOLDER
    )
    await db.insert_scan_config(estado.resultado_final.mejor_config.model_dump(mode="json"))
    await db.insert_backtest_run(backtest_run.model_dump(mode="json"))
    estado.guardado = True
    return RedirectResponse("/optimize?guardado=1", status_code=303)
