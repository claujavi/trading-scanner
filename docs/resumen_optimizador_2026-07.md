# Resumen — Optimización del scanner (jul 2026)

> **⚠️ OBSOLETO (2026-08-03).** Este run se calculó con dos bugs de "día NY vs UTC" todavía
> presentes en `history_cache.py::filter_range()` y `backtest/runner.py::_valor_asof()` — ambos
> afectaban directamente la clasificación (cruce_ema, sobre_sma200, atr_pct) y la simulación de
> posición (entrada/stop/target) que Optuna usó para elegir estos parámetros. Con `n=7` trades ya
> señalado como muestra chica más abajo, no solo las métricas sino la propia config ganadora quedan
> en duda. Ambos bugs están corregidos (ver `docs/spec_modulo_3bp_4bp.md`, checkpoint del paso 4) y
> hay una re-corrida en curso — ver `docs/resumen_optimizador_2026-08.md` cuando termine. Se deja
> este documento como registro histórico del trabajo de infraestructura del optimizador (sigue
> siendo válido, no tocó nada de esto), no como fuente de calibración.

Contexto para retomar la conversación sobre calibración de parámetros del trading scanner.

## Qué se hizo

**1. Precarga histórica completa** (`cli_precarga.py`, nuevo):
- Diario (`d`): 279+ tickers desde 2023-01-01 hasta hoy.
- Intradía (`4h`/`15m`/`5m`): desde 2025-11-01 (límite real de profundidad de Schwab, confirmado empíricamente — pedir más atrás no trae nada, Schwab trunca en silencio).
- Corrida en tandas manuales con backoff ante rate-limit, sin incidentes mayores.

**2. Actualización diaria automática del cache** (`history_cache.actualizar_hasta_hoy()`):
- Cada scan en vivo (`pipeline.py::process_ticker`) ahora mantiene `backtest_data/` al día solo — ticker nuevo → backfill completo; ticker conocido → refresca solo el mes en curso.
- Cache negativo de meses sin datos (`_marcar_meses_sin_datos`): si Schwab confirma que no tiene historial de un mes (instrumento recién listado, o hueco puntual sin operaciones), se marca con un Parquet vacío para no volver a pedirlo nunca más.

**3. Optimizador — de inviable a funcional:**
El primer intento de correr 50 trials sobre 287 tickers x 3.5 años **no terminó ni el primer trial en 22+ horas**. Causas encontradas y corregidas, en orden:
- El backtest lanzaba una tarea por cada combinación (ticker × día) — 267.000+ tareas por trial. Se rediseñó para evaluar por ticker (contexto cargado una sola vez, después se recorren los días en memoria).
- Bug de schema (Int64 vs Float64 en la columna `volume`) al mezclar meses reales con meses marcados vacíos — corregido.
- Bug de alineación de índice de pandas en `calc_atr_pct` cuando el DataFrame tenía índice de fecha en vez de índice 0..n — corregido sin tocar `indicators/`.
- Cuello de botella de CPU: cada día recalculaba EMA/SMA/ATR desde cero (933 veces por ticker). Se vectorizó — se calcula la serie completa **una sola vez por ticker** y se busca el valor de cada día (`_valor_asof`). Matemáticamente válido porque EMA/ATR convergen mucho antes de la ventana de contexto usada (~400 días), y SMA ya depende solo de la ventana fija sea cual sea el historial total.
- **HV Rank deliberadamente NO se vectorizó**: a diferencia de EMA/ATR, rankea el valor de hoy contra el mínimo/máximo de TODA la ventana que se le pase (no una ventana fija) — vectorizarlo cambiaría el resultado, no solo la velocidad. Se prefirió exactitud sobre velocidad ahí.
- Cada paso de esta optimización se validó con tests de equivalencia (comparar valor por valor contra el método viejo) antes de confiar en él — el patrón atrapó los dos bugs reales mencionados arriba antes de que llegaran a producción.
- Se agregó persistencia de Optuna en SQLite (`optimizer_state/`, flag `--study-name`) para poder retomar un run interrumpido sin perder los trials ya hechos.

Resultado: de "no termina en 22+ horas" a **~9 horas estimadas** para 50 trials sobre el universo completo (287 tickers, 2023-2026). Se corrió y terminó exitosamente.

## Resultado del optimizador (universo curado, 50 trials)

**Config ganadora — ya guardada en Turso (`scan_configs` + `backtest_runs`), activa hoy:**

| Parámetro | Valor |
|---|---|
| relvol_umbral_day | 4.76 |
| relvol_umbral_swing_min / max | 2.65 / 3.15 |
| atr_pct_umbral_day | 4.78 |
| atr_pct_umbral_swing_min / max | 2.98 / 4.97 |
| ivr_umbral_compra / venta | 13.8 / 25.7 |
| **umbral_decision** | **4.76** (alto — ver hallazgo abajo) |
| rr_target | 2.71 |
| stop_atr_multiplicador | 1.08 |
| slippage_bps | 6.38 |

**Métricas del trial ganador:** 7 trades, 71.4% win rate, profit factor 9.06, expectancy 0.476 R/trade, max drawdown 0.41 R.

**Hallazgo real (no ruido, se repite en los 7 mejores trials):** `umbral_decision` entre 4.6-5.0 da pocos trades pero consistentemente rentables. Por debajo de ~4.0, el volumen de trades explota (cientos a miles) pero el resultado es catastrófico (fitness hasta -105). Por encima de ~5.0, no pasa nada (0 trades, fitness -inf). El sistema, tal como está calibrado hoy, funciona mejor siendo muy selectivo.

## Por qué no hay que confiar ciegamente en este número todavía

1. **El universo "curado" no imita la exposición real.** Son 287 tickers simultáneamente elegibles los 3.5 años — en la vida real, el Stock Hacker de ToS ya pre-filtra a ~10-30 candidatos por día. El hallazgo "ser laxo pierde plata" podría ser en parte un artefacto de esta exposición artificialmente inflada, no una propiedad real de la estrategia en producción. CLAUDE.md ya documentaba este riesgo del universo curado; **falta la validación contra `universo_real`**, que todavía no tiene suficientes días de CSV acumulados.
2. **Muestra chica (n=7).** Profit factor 9 con 7 trades tiene varianza enorme — reproducible en un clúster de trials vecinos, pero sigue siendo poca evidencia dura.
3. **El fitness no tiene piso duro de trades mínimos**, solo penalización gradual (`trades_objetivo=30`) — no alcanzó para hacer atractiva ninguna config de "muchos trades" porque genuinamente pierden plata en este universo, pero no sabemos si eso se sostiene en universo real.

## Recomendación / próximos pasos

1. Seguir operando con la config guardada (es un punto de partida razonable), pero **tratarla como hipótesis direccional, no calibración final.**
2. En cuanto se acumulen semanas de CSV reales operando el sistema, correr el optimizador contra `--universo real` y comparar si el mismo patrón (selectividad alta gana) se sostiene con la exposición diaria real, no la inflada.
3. Si se vuelve a correr sobre curado mientras tanto, considerar agregar un piso duro de trades mínimos al fitness (no solo penalización gradual) para no premiar configs con muestras tan chicas.
4. No optimizar los `peso_*` todavía — sigue esperando los 60+ días de operación real que ya pedía CLAUDE.md desde antes.

## Notas técnicas para retomar

- Study de Optuna persistido en `optimizer_state/optuna.db3`, nombre `curado_v2` — se puede re-analizar con `optuna.load_study(study_name="curado_v2", storage="sqlite:///optimizer_state/optuna.db3")`.
- El comando completo para repetir/extender este run (ver historial de conversación para la lista completa de 287 tickers).
- Tests de equivalencia nuevos: `tests/unit/test_runner_equivalencia_pandas.py`, `tests/unit/test_runner_equivalencia_end_to_end.py`.
