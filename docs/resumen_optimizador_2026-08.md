# Resumen — Optimización del scanner (ago 2026), re-corrida post-fix

Re-corrida de `docs/resumen_optimizador_2026-07.md` (marcado obsoleto) después de corregir los dos
bugs de "día NY vs UTC" (`history_cache.py::filter_range()` y `backtest/runner.py::_valor_asof()`,
ver `docs/spec_modulo_3bp_4bp.md`, checkpoint del paso 4).

## Parámetros de la corrida

- Universo curado: 355 tickers (todos los cacheados al 2026-08-03, creció de los 287 de julio),
  2023-01-01 a 2026-08-03.
- 50 trials, `trades_objetivo=30` (default), `study_name=curado_v3_fix_dia` (persistido en
  `optimizer_state/optuna.db3`, separado del `curado_v2` de julio).
- Corrida por CLI (`trading-scanner-optimize`), en background, 2026-08-03 13:38 → 21:54 (~8h16m).
- Nota de infraestructura: hubo un corte de conexión a internet desde ~17:18 en adelante (4
  tickers — CKHUF, KPELF, PIAIF, STOSF — con fallas de DNS repetidas en cada trial). No afectó el
  resultado: el backtest corre 100% sobre Parquet local, esos 4 tickers (de 355) simplemente se
  excluyeron del contexto en los trials afectados, sin contaminar el cache negativo (la falla
  transitoria no se cachea como "sin historial confirmado", por diseño).

## Resultado — config ganadora (NO guardada en Turso todavía, pendiente de decisión)

| Parámetro | Valor |
|---|---|
| relvol_umbral_day | 5.81 |
| relvol_umbral_swing_min / max | 2.95 / 3.78 |
| atr_pct_umbral_day | 4.55 |
| atr_pct_umbral_swing_min / max | 2.98 / 3.37 |
| ivr_umbral_compra / venta | 10.7 / 12.4 |
| umbral_decision | 3.07 |
| rr_target | 3.77 |
| stop_atr_multiplicador | 2.74 |
| slippage_bps | 14.9 |

**Métricas objetivas:** 15 trades, 73.3% win rate, profit factor 2.31, expectancy 0.097 R/trade,
net profit 1.45 R, avg win 0.233 R, avg loss -0.277 R, max drawdown 0.74 R.

## Comparación contra el run de julio (obsoleto, con bugs)

| | Julio (bugs presentes) | Agosto (fix aplicado) |
|---|---|---|
| Trades | 7 | 15 |
| Win rate | 71.4% | 73.3% |
| Profit factor | 9.06 | 2.31 |
| Expectancy | 0.476 R/trade | 0.097 R/trade |
| Max drawdown | 0.41 R | 0.74 R |
| umbral_decision | 4.76 (muy selectivo) | 3.07 (bastante menos selectivo) |

**Confirma la sospecha:** los bugs de fecha inflaban las métricas de julio de forma sustancial —
el profit factor de 9.06 no era real. El resultado corregido sigue siendo positivo (PF > 1, win
rate alto), pero mucho más modesto. El win rate se mantuvo estable entre ambas corridas — el
patrón de selectividad (menos trades, mejor calidad) sigue apareciendo, pero con una magnitud muy
distinta.

## Por qué seguir sin confiar ciegamente en este número

Los mismos tres motivos que ya valían para julio, más dos hallazgos nuevos encontrados al mirar
los 15 trades uno por uno (2026-08-04):

1. **Universo curado no imita la exposición real** — 355 tickers simultáneamente elegibles 3.5
   años vs. los ~10-30 candidatos/día reales del Stock Hacker de ToS. Falta validar contra
   `universo_real` cuando haya más días de CSV acumulados.
2. **Muestra chica, y más chica de lo que parece.** `n=15` es mejor que `n=7`, pero los 15 trades
   caen **todos entre enero y julio de 2026** — nada en 2023, 2024 ni 2025, pese a que el rango
   pedido fue 2023-01-01 a 2026-08-03. Motivo: `simular()` necesita velas de 5m del día exacto de
   la señal, y Schwab solo tiene intradía cacheado desde noviembre 2025 (límite real de
   profundidad de la API, ya documentado en CLAUDE.md). La clasificación corrió sobre los 3.5 años
   completos, pero la simulación de posición —lo que genera un trade con resultado medible— solo
   pudo materializarse en esta ventana real de ~9 meses. Es "15 trades en 9 meses", no "15 en 3.5
   años".
3. **Sin piso duro de trades mínimos en el fitness**, solo penalización gradual.
4. **El target y el stop de esta config, en la práctica, nunca se usan — los 15 trades cerraron el
   100% por `eod`** (cierre forzado 15:55 ET), ninguno tocó `target` ni `stop`. Con
   `stop_atr_multiplicador=2.74` y `rr_target=3.77`, el target queda a `stop_dist × rr_target ≈
   10.3 × ATR` de la entrada — pedirle al precio moverse >10x su rango diario típico dentro de una
   sola sesión es virtualmente imposible, y el stop (2.74x ATR, ancho para un stop intradía) casi
   nunca se toca tampoco. Optuna encontró que ensanchar ambos hasta volverlos inalcanzables (en
   los hechos, "comprar en la apertura y sostener hasta el cierre forzado") rinde mejor que dejar
   que el mecanismo FIXED_RR intervenga de verdad — no es que el modo de salida "funcionó", es que
   quedó desactivado de facto.
5. **Hallazgo de fondo, más allá de esta corrida puntual: el simulador no distingue DAY de SWING.**
   De los 15 trades, la mayoría están clasificados `SWING` (CVE, BILI, STM, NOK, EQNR, GIS, TEVA,
   GMAB, CPRT, NKE) pero se simularon idénticos a los `DAY` — entrada en la apertura, cierre
   forzado el mismo día. Un SWING debería poder sostenerse varios días; hoy el sistema nunca prueba
   eso. Decisión tomada para corregirlo (agregar corte a 15 días hábiles para SWING en vez de
   cierre el mismo día) — ver `docs/backlog_mejoras_clasificador.md`, Prioridad 3.5. Implica que
   este resultado (y el de julio) subestiman lo que un SWING real podría rendir sosteniendo la
   posición más de un día.

## Simulación ilustrativa en dólares (no es un output nativo del sistema)

El sistema no trackea capital/position sizing (ver CLAUDE.md) — esto es una extrapolación externa,
no un cálculo del backtest. Arrancando con **$200**, arriesgando `riesgo_por_operacion_pct=1%` del
capital vigente por trade, aplicando los 15 `resultado_r` reales en orden cronológico: **capital
final ≈ $202.91** (+1.45% en ~7 meses), **max drawdown ≈ $0.92 (0.46%)** — nunca cerca del corte de
pérdida máxima diaria (3% ≈ $6) ni de ningún riesgo de no poder seguir operando. Ver el detalle
trade por trade en la conversación del 2026-08-04.

## Pendiente de decisión

- **¿Guardar esta config como activa en Turso?** No se guardó todavía — queda a criterio del
  trader, no se decide solo. **Corrección respecto a la primera versión de este documento:** la
  config activa en Turso al momento de esta corrida no era la de julio, sino el default de
  `ScanConfig()` (`config_base.nombre == "default"`) — la config ganadora de julio nunca llegó a
  guardarse, pese a lo que se había asumido. A confirmar el estado real en `/config` antes de dar
  por buena esta afirmación.
- Re-evaluar esta config (o correr una nueva) después de implementar el corte a 15 días hábiles
  para SWING (Prioridad 3.5 del backlog) — los números de acá subestiman el rendimiento real de
  las señales SWING.
- Seguir acumulando CSV reales para poder correr contra `--universo real`.
