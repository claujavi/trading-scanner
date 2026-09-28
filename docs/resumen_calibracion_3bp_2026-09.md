# Resumen — Calibración y validación del módulo 3BP/4BP (sep 2026)

Cierra el paso pendiente de `docs/spec_modulo_3bp_4bp.md` sección 8 (calibración de `bp34_*`).
Cubre tres rondas sucesivas sobre el mismo universo curado (~470-480 tickers cacheados,
2025-11 → 2026-08): la calibración original sin costos, la corrección de costos/horario, y la
simulación de cuenta que responde la pregunta real del trader ("¿esto se puede operar sin romper
la cuenta?"). Cada ronda corrigió un problema real encontrado en la anterior — se documentan todas
porque el camino importa tanto como el resultado final.

---

## Ronda 1 (2026-09-09/22) — calibración original, sin costos

`optimizer/cli_3bp.py` (`trading-scanner-optimize-3bp`), studies `3bp_15m_sin_drawdown` y
`3bp_5m_sin_drawdown`, 50 trials c/u.

| | 15m | 5m |
|---|---|---|
| Trades | 5340 | 7165 |
| Win rate | 36.3% | 32.8% |
| Profit factor | 1.42 | 1.39 |
| Expectancy | 0.235 R | 0.239 R |

Parecía un resultado sólido — hasta que se buscó un filtro extra mirando qué distinguía las
entradas ganadoras de las perdedoras (ver sección siguiente).

## Ronda 1.5 — búsqueda de filtros extra, y el hallazgo del problema real

Se probó correlacionar el resultado (TARGET/STOP) contra: cruces de EMA 9/21 en los 4 timeframes,
posición sobre SMA200/EMA50, RelVol y ATR% del día, tier confirmado/sin_confirmar, y un campo nuevo
agregado para esto (`Bp34Evento.barra1_wrb_ratio` = tamaño de la barra 1 relativo al ATR14 al
detectarla, commit `5fcec51`).

- **Sin señal:** cruces EMA, SMA200/EMA50 — diferencias de 1-5 puntos entre TARGET y STOP.
- **Con señal (pero engañosa, ver más abajo):** ATR%_dia≥8 (PF 1.54) y `barra1_wrb_ratio`≥7-9
  (PF hasta 1.93) parecían filtros útiles.
- **Tier al revés:** `sin_confirmar` rendía mejor que `confirmado` — no investigado a fondo.

**El hallazgo que cambió todo:** desglosando por distancia al stop, el edge bruto vivía casi
entero en entradas con stop <0.3% del precio (n=1264 de 5m, +1.04R bruto) — donde 10 bps de
slippage ida-y-vuelta se comen la mitad del riesgo. Con costos reales:

| Costo (round-trip) | Expectancy global 5m | Expectancy global 15m |
|---|---|---|
| 0 bps (bruto, como reportó el optimizador) | +0.244 R | +0.224 R |
| 10 bps | **+0.016 R** | +0.050 R |
| 20 bps | −0.212 R | −0.123 R |

El PF de 1.39-1.42 de la Ronda 1 no era falso, pero no se podía cobrar: `walker_3bp.py` ignoraba
`ScanConfig.slippage_bps` y modelaba stop = exactamente −1R. El `barra1_wrb_ratio`≥7 tampoco
sobrevivía solo: con stop≥0.6% (tradable) aportaba poco (0.052→0.059R); combinado con ATR%≥8 sí
se sostenía (n=595, +0.159R bruto, +0.106R a 10 bps) pero dejaba solo el 12% de las señales.

Spread real medido en 45 CSV de ToS guardados (972 filas con Bid/Ask): mediana 43.6 bps — 10-20 bps
de costo round-trip es un supuesto razonable, no conservador de más.

## Ronda 2 (2026-09-24/25) — costos reales + descubrimiento del filtro de horario

**Fix 1 — slippage y stop mínimo** (commit `0fb3751`): `walker_3bp._resolver_entrada` aplica
`slippage_bps` por lado (misma convención que `simulator.py`); `ScanConfig.bp34_stop_min_pct`
descarta entradas con stop más corto que ese % del precio, en backtest y en vivo.

**Hallazgo 2 al medir el efecto por franja horaria:** el 60% de TODAS las entradas (5m y 15m) caían
en pre-market/madrugada (hasta 00:15 NY) — las velas de Schwab traen horario extendido y el walker
corría el detector desde la primera vela del día. Era justo el tramo con más edge bruto (+0.37R) y
menos operable. Intentar arrancar el detector recién a las 9:30 casi eliminó las señales (72 vs
~380 esperadas en una prueba de 60 tickers): la "barra ancha" del patrón suele ser la propia barra
de apertura contra un ATR de pre-market chico — el contexto de pre-market es parte del patrón, no
ruido a descartar.

**Fix 2 — sesión regular con contexto** (commit `778d74d`): `ScanConfig.bp34_entradas_solo_sesion_regular`
alimenta el detector desde las 4:00 NY pero solo acepta ENTRADAS 9:30-16:00;
`bp34_ventana_entrada_minutos` (default 90 = hasta las 11:00, donde cae el 85% de las entradas
regulares) acota más. De paso, `_ContextoIncremental` reemplaza el cálculo de ATR14/volumen
promedio por barra (antes reconvertía toda la lista a DataFrame en cada vela, ~1ms×barra,
cuadrático por día — el 95% del tiempo de un trial) por una fórmula incremental O(1), verificada
idéntica con un test. Resultado: de ~45s/ticker a ~1s/ticker — un trial de 5m con 470 tickers pasa
de ~3.5h a ~6-8min.

**Recalibración con costos + sesión regular** (studies `3bp_15m_costos_rth` / `3bp_5m_costos_rth`,
`--slippage-bps 5 --stop-min-pct 0.6`, ventana 90 min, 50 trials c/u):

| | 15m | 5m |
|---|---|---|
| Trades | 1867 | 2229 |
| Win rate | 46.8% | 39.4% |
| Profit factor | 1.25 | 1.17 |
| Expectancy | **0.095 R** | **0.093 R** |
| wrb_multiplicador | 2.77 | **1.02 (pegado al piso del rango 1.0-4.0 — revisar)** |
| tolerancia_pct | 0.051 | 0.076 |
| n_invalidacion | 3 | 7 |
| target_r | 4.70 | 3.87 |
| ventana_inicio_barras | 5 | 5 |
| volumen_confirmado_mult | 3.49 | 1.57 |

Ya no es el +0.24R "bonito" de la Ronda 1, pero es un número que sobrevive costos reales.

## Ronda 3 (2026-09-28) — simulación de cuenta (la pregunta que realmente importa)

Ni el profit factor ni la expectancy en R dicen si esto se puede operar sin romper la cuenta —
`max_drawdown_r` del walker es la suma de todos los trades de 470+ tickers tratados como una sola
curva secuencial, algo que ningún trader hace (ver `docs/backlog_mejoras_clasificador.md` para el
mismo problema ya resuelto para el clasificador de 6 criterios). Se simuló una cuenta real:
riesgo ≤1% por trade dimensionado con el equity al inicio del día, **sin apalancamiento** (nocional
≤ equity/3 — con stops muy cortos el riesgo real baja del 1% nominal), máximo 3 posiciones
simultáneas, corte diario si las pérdidas ya cerradas llegan al 3%, orden real de llegada de las
señales por timestamp.

| | 15m sola | 5m sola |
|---|---|---|
| Eventos / días activos | 1895 / 188 de 209 | 2268 / 192 de 206 |
| Retorno del período (~9-10 meses) | **+89.1%** | +56.6% |
| Drawdown máximo real | **13.6%** | 20.6% |
| Bootstrap DD mediana / p95 (3000 remuestreos) | 12.9% / 22.2% | 17.2% / 30.3% |
| P(retorno < 0) | 1% | 6% |
| Anualizado extrapolado (NO garantía) | +116%/año | +72%/año |

**15m gana en las dos dimensiones — más retorno y menos riesgo.** Ver la sección de próximos pasos
sobre por qué no adoptarlo todavía sin más validación.

### 15m + 5m combinadas vs. solo 15m con más riesgo

Pregunta del trader: ¿conviene correr los dos timeframes juntos compitiendo por los mismos 3 slots
de la cuenta, o quedarse con uno solo?

| Variante | Retorno | DD máx. | Bootstrap DD p95 | P(perder) |
|---|---|---|---|---|
| 15m sola | +89.1% | 13.6% | 22.2% | 1% |
| 5m sola | +56.6% | 20.6% | 30.3% | 6% |
| 15m + 5m combinadas (3 slots compartidos) | +110.8% | 18.5% | 27.5% | 1% |
| **15m sola, riesgo ≤2%/trade** | **+158.8%** | **15.7%** | 24.8% | **0%** |

Al competir por los mismos slots solo entra el 18% de las señales de 15m y el 27% de las de 5m —
la mayoría queda afuera porque los slots ya están ocupados. Combinar mejora el retorno frente a
15m sola (más oportunidades entre las que elegir) pero también sube el drawdown (5m aporta stops
más frecuentes y ajustados). **Usar ese mismo capital ocioso para ampliar el riesgo de 15m sola
(en vez de sumar una señal peor) rinde más Y con menos riesgo que combinar timeframes** — resultado
esperable dado que 15m ya viene con mejor PF y win rate individualmente. **No se recomienda operar
5m — no aporta nada que 15m con más tamaño no haga mejor**, con la reserva de la sección siguiente
sobre no llevar la simulación de "más riesgo" a producción sin pensarlo más (position sizing ideal,
sin correlación entre posiciones del mismo día, muestra de 9 meses).

---

## Qué falta antes de operar esto en serio

1. **El vivo no filtra por horario todavía.** `bp34_entradas_solo_sesion_regular` solo se aplicó al
   walker de backtest (`walker_3bp.py`); `main.py`/`market_data_cache.py` (wireo en vivo) sigue
   emitiendo eventos ENTRADA a cualquier hora. Si se adopta esta calibración, hay que llevar la
   misma regla al vivo — si no, lo que se opera no es lo que se calibró.
2. **`wrb_multiplicador=1.02` en 5m está pegado al piso del rango de búsqueda** (1.0-4.0) — no
   investigado si el óptimo real cae fuera del rango o si es sobreajuste. Ya no importa tanto dado
   que no se recomienda operar 5m, pero documentado por si se retoma.
3. **Revalidar contra `universo_real`** (tickers que salieron de verdad en los CSV de ToS
   guardados, no el universo curado de 470+ nombres ya sabidos como volátiles) — mismo caveat que
   arrastra el proyecto desde la calibración del clasificador de 6 criterios en agosto.
4. **Muestra de ~9-10 meses** (nov 2025 - ago 2026) — corta para conclusiones fuertes, un solo
   régimen de mercado. El "anualizado" es una extrapolación matemática de esos 9 meses, no una
   proyección real.
5. **La simulación de cuenta usa position sizing ideal** (fracciones exactas de equity, sin
   redondeo a cantidad de acciones enteras) y no modela correlación entre posiciones abiertas el
   mismo día (varios tickers moviéndose juntos en un día de mercado direccional). Ambos sesgan el
   resultado optimista, en un grado no cuantificado.
6. **La variante "15m con riesgo ≤2%" no fue calibrada como tal** — es la misma señal de 15m con
   el dial de riesgo subido, no una recalibración de `bp34_*` pensada para ese nivel de riesgo.

## Scripts usados (no versionados, en el scratchpad de la sesión — no en el repo)

Todo el análisis de correlación, cuantificación de costos y simulación de cuenta se hizo con
scripts ad-hoc fuera del repo (correlacion_3bp_*.py, cuantificar_filtro_atr.py, costos_stop.py,
simular_cuenta*.py). Si se decide formalizar alguno de estos análisis como herramienta reusable
(en particular la simulación de cuenta — sería el análogo de `backtest/simulator.py` pero a nivel
de cartera, no de trade individual), es trabajo nuevo, no algo ya hecho en el repo.
