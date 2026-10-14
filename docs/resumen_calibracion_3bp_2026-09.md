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

## Ronda 4 (2026-09-28) — cuenta en dólares, ajuste de riesgo, redondeo real y precio de los nombres

Preguntas concretas del trader sobre la simulación de cuenta de la Ronda 3, todas sobre 15m (la
recomendada), capital inicial $300, mismos supuestos de siempre salvo que se indique lo contrario.

### Cuenta a $300, estrategia recomendada (1% de riesgo, capitalizando a diario)

Equity final: **$567** (x1.89) en los ~9-10 meses simulados, DD máximo real 13.6%. Bootstrap (1500
remuestreos de días): mediana $545, p10 $396, solo 1% de los caminos termina por debajo de los $300
iniciales — resultado razonablemente robusto al orden en que cayeron los días buenos/malos.

### ¿Riesgo fijo en dólares para siempre, o reajustado cada N semanas?

| Régimen (riesgo 2%, para que se note el efecto) | Equity final | DD máx |
|---|---|---|
| Fijo sobre $300 (nunca se ajusta) | $643 (x2.14) | 13.7% |
| Reajustado cada 13 semanas | $729 (x2.43) | 16.0% |
| Reajustado cada 4 semanas | $753 (x2.51) | 15.6% |
| Reajustado cada 2 semanas | $762 (x2.54) | 15.8% |
| Compuesto a diario | $776 (x2.59) | 15.7% |

El drawdown casi no cambia entre regímenes — lo que cambia es la velocidad de crecimiento.
Reajustar cada 4 semanas ya captura casi toda la ventaja de capitalizar a diario, con mucho menos
trabajo operativo. El "fijo para siempre" es el más simple de ejecutar pero crece ~15% más lento
en este período.

**Extrapolación matemática a 5 años (NO una predicción — ver caveats):** remuestreando por bloques
semanales reales (bootstrap, no una tasa fija) hasta cubrir 260 semanas, 400 caminos:

| Régimen (riesgo 2%) | Mediana a 5 años | p10 – p90 |
|---|---|---|
| Fijo sobre $300 | $3,564 | $2,773 – $4,274 |
| Reajustado cada 4 semanas | **$47,755** | $16,401 – $130,230 |

A 9 meses la diferencia entre fijo y capitalizado era marginal; a 5 años se vuelve de un orden de
magnitud completo — crecimiento lineal vs. exponencial. **Esto no es una predicción real**: asume
sin decaimiento de la ventaja, sin límite de capacidad/liquidez al crecer el tamaño de la cuenta
(con $47k en microcaps de baja liquidez el trader empieza a mover el precio con su propia orden,
algo que el modelo no contempla), sin cambio de régimen de mercado, y es literalmente la misma
ventana de 9 meses repetida. Conclusión útil que sí se sostiene: cuanto más largo el horizonte,
más importa reajustar el riesgo — no fijarlo para siempre.

### Redondeo real a acciones enteras (no fraccionarias)

Implementada la fórmula ya documentada en la Prioridad 4 de este backlog (`cantidad_acciones =
round(riesgo_$ / distancia_al_stop)`, redondeo estándar):

| Régimen | Ideal (fraccionario) | Real (acciones enteras) |
|---|---|---|
| 1% fijo | $512 | $571 |
| 1% cada 4 semanas | $562 | $626 |
| 2% fijo | $643 | $709 |
| 2% cada 4 semanas | $753 | $859 |

El redondeo real dio *mejor* resultado que el sizing ideal en esta muestra — pero es ruido de
cuantización, no una ventaja real: redondear 0.7 acciones a 1 entera implica arriesgar 43% más de
lo planeado en ese trade puntual, y acá ese ruido jugó a favor por casualidad de la secuencia, no
por diseño. Dato sólido y no ambiguo: **solo 1% de las señales (17-21 de 1895) quedó descartada por
no alcanzar ni para 1 acción** — con $300 y stops típicos de centavos, el redondeo no es un
problema serio de cantidad de trades ejecutables.

### ¿El edge se sostiene en acciones de precio más alto / más líquidas?

El universo cacheado (483 tickers) está fuertemente inclinado a precios bajos (mediana $12.1);
solo 30 tickers cotizan ≥$50 y 14 ≥$100 (agosto 2026). De mega-caps reales solo están cacheadas
AAPL y MSFT — faltan GOOGL, AMZN, NVDA, META, TSLA, JPM, V, UNH y el resto.

Desglosando las 1895 señales de 15m por precio de entrada:

| Precio de entrada | n | Win rate | PF | Expectancy |
|---|---|---|---|---|
| $0-20 | 1275 | 47.0% | 1.40 | **+0.155 R** |
| $20-50 | 445 | 47.0% | 0.96 | -0.014 R |
| $50-100 | 103 | 45.6% | 0.93 | -0.025 R |
| $100+ | 72 | 44.4% | 1.22 | +0.081 R |

**Todo el edge positivo está concentrado en el tramo <$20.** El tramo $20-100 da negativo. El de
$100+ vuelve a ser positivo pero con muestra chica (72 trades) y mezclando nombres volátiles que
puntualmente cotizaron caro (AEHL, FCUV, WETO, VEEE) con algunos conocidos (AAPL, MSFT, PLTR, SHOP,
SNOW) — no es evidencia de que el patrón funcione en large caps líquidas de verdad. Esperable: los
`bp34_*` se calibraron sobre una mezcla dominada por nombres baratos y volátiles, sin motivo para
esperar que transfieran a un régimen de menor volatilidad relativa.

**No es algo que se resuelva filtrando los datos ya generados** — haría falta (1) precargar un
universo de 50-100 acciones grandes y líquidas reales (`trading-scanner-precargar-historico`) y
(2) recalibrar `bp34_*` específicamente para ese universo, no reusar los parámetros de microcaps.
Relevante para cuando la cuenta crezca lo suficiente como para necesitar nombres más líquidos (el
Stock Hacker de ToS que alimenta el CSV diario, fuera del alcance de este repo, sería el lugar
natural para ampliar el criterio de selección en ese momento — no `ScanConfig`, que ya tiene
`precio_max=500` bastante amplio y que además `walker_3bp.py` ni siquiera aplica hoy).

**Status: identificado, no implementado.** Pendiente nuevo, en la misma categoría que la
revalidación contra `universo_real`.

---

## Ronda 5 (2026-09-28) — corrección del hallazgo de `tier`, y un filtro que sí funciona

La Ronda 1.5 había encontrado que `sin_confirmar` rendía *mejor* que `confirmado` (exp 0.269R vs
0.205R) — contraintuitivo, quedó sin investigar. Repetido sobre los eventos de la calibración
recomendada (costos reales + RTH, study `3bp_15m_costos_rth`), **el resultado se invierte por
completo**:

| | 15m confirmado | 15m sin_confirmar |
|---|---|---|
| n | 1185 | 710 |
| Win rate | 47.7% | 45.4% |
| Profit factor | 1.39 | 1.06 |
| Expectancy | **+0.151R** | +0.022R |

Se sostiene en las dos mitades del período (split en 2026-04-14). No es un efecto de pocos
tickers dominando la muestra (391 tickers distintos en `confirmado`, top 5 concentra solo 3%). En
5m es menos consistente (se invierte entre mitades) — no se usa como base para decidir nada ahí,
dado que 5m ya no se recomienda operar.

**Por qué se invirtió:** el hallazgo original de la Ronda 1.5 corría sobre datos sin costos, sin
filtro de horario y con la calibración vieja — mezclaba entradas de pre-market/madrugada que
después se identificaron como no operables (Ronda 2). Con eso limpio, el resultado pasa a ser el
intuitivo: la ruptura con volumen fuerte confirma mejor que una floja.

**Cuantificado en la cuenta de $300 (15m, 1% capitalizando):** filtrar a solo `tier="confirmado"`
mejora las dos dimensiones a la vez, sin trade-off (a diferencia de ATR%/WRB, que cambian cantidad
por calidad):

| | Todos | Solo `confirmado` |
|---|---|---|
| Señales | 1895 | 1185 (63%) |
| Equity final | $567 (x1.89) | **$669 (x2.23)** |
| Drawdown máx. real | 13.6% | **10.1%** |
| Bootstrap DD mediana / p95 | 12.8% / 21.8% | 10.5% / 17.6% |
| P(terminar por debajo de $300) | 1% | 0% |

**Status: implementado (2026-09-29).** `ScanConfig.bp34_solo_tier_confirmado` (default `False`)
descarta entradas `sin_confirmar` en backtest (`walker_3bp._caminar_dia`) y en vivo (`main.py::
_on_evento_3bp`), mismo patrón que `bp34_stop_min_pct`. `trading-scanner-optimize-3bp` gana
`--solo-confirmado/--sin-filtrar-tier`. Config activa actualizada (`scan_configs` id=11,
`bp34_costos_rth_tier_confirmado_2026-09-29`) con el filtro encendido, sobre la config de la Ronda
2/3 (costos + sesión regular). 4 tests nuevos.

---

## Ronda 6 (2026-10-01/13) — bug real del stop: invalida las Rondas 1-5, y el fix lo corrige

### El bug

Revisando el primer trade en vivo con la config de la Ronda 5 (BZ, 15m, entry=14.56, stop=14.14),
el trader pegó el texto original del curso (Live Traders, capítulo "3 & 4 Bar Plays"), que dice:

> "Bar #3 or #4 is the trigger bar (entry & expansion bar), the stop loss goes under the lowest
> bar (Bar #2 or Bar #3)"

Es decir: el stop va bajo el low del **grupo** (barra 2, o 2-3), no bajo la barra 1. Nuestra propia
spec (`docs/spec_modulo_3bp_4bp.md`) dice exactamente lo mismo: "Stop: mínimo del grupo de barras
(2, o 2-3)". El código, sin embargo, hacía:

```python
stop = min([self._barra1.low] + [b.low for b in self._grupo])
```

**Prueba matemática de que esto era siempre `barra1.low`, nunca el grupo:** la condición para que
una barra entre al grupo (`_bar_confirma_grupo`) exige `vela.low >= punto_medio_barra1`, y
`punto_medio_barra1 = barra1.low + 0.5×rango_barra1 > barra1.low` siempre (barra1 tiene rango
positivo por ser WRB). Por construcción, el low de cualquier barra del grupo es **siempre mayor**
que `barra1.low` — el término del grupo nunca podía ganarle a `barra1.low` en ese `min()`. El stop
quedaba siempre más ancho de lo que pide tanto el curso como la propia spec del proyecto. No había
ningún comentario ni commit que documentara esto como decisión deliberada (el commit original,
`964f209`, documenta otras dos interpretaciones no literales de la spec, pero no esta).

**Segundo gap relacionado:** la spec dice que 3BP debería reusar la regla R2 del clasificador de 6
criterios (`stop = max(ATR14×1.5, nivel_técnico)`) — ese piso de ATR nunca se había implementado
para 3BP, solo existía el nivel técnico (y encima mal calculado).

**Por qué invalida las Rondas 1-5:** el stop alimenta `target = entry + (entry-stop)×target_r`, y
el R de cada trade se mide contra `entry-stop`. Con el stop sistemáticamente más ancho, todas las
cifras de expectancy/PF/win rate/la cuenta de $300/los filtros de ATR%/WRB/tier de las Rondas 1-5
quedan calculadas sobre un stop distinto al correcto. La metodología (walker, costos, filtro de
horario, simulación de cuenta) sigue siendo válida — los números puntuales, no.

### El fix, en dos pasos

**Paso 1 — stop = mínimo del grupo, sin barra 1** (commit pendiente al cerrar esta ronda):
```python
stop = min(b.low for b in self._grupo)
```
Recalibración completa (studies `3bp_15m_stop_fix_v1` / `3bp_5m_stop_fix_v1`, mismos flags que la
Ronda 2/3/5: `--slippage-bps 5 --stop-min-pct 0.6 --solo-confirmado`, sesión regular 90min):

| | 15m | 5m |
|---|---|---|
| Trades | 1758 | 3173 |
| Win rate | 32.8% | 25.9% |
| Profit factor | **0.92** | **0.88** |
| Expectancy | **-0.055R** | **-0.095R** |
| Net profit | -97.2R | -300.8R |

**Resultado: con el stop corregido (sin el piso de ATR todavía), la expectativa da negativa en los
dos timeframes.** El edge positivo de las Rondas anteriores era, en gran parte, un artefacto del
stop mal puesto.

**Paso 2 — agregar el piso de ATR14×1.5 (regla R2)**, reusando `ScanConfig.stop_atr_multiplicador`
(campo ya existente, compartido con el clasificador de 6 criterios):
```python
stop_tecnico = min(b.low for b in self._grupo)
distancia_tecnica = entry - stop_tecnico
distancia_minima = stop_atr_multiplicador * atr14  # atr14 de la barra gatillo
stop = entry - max(distancia_tecnica, distancia_minima)
```
Recalibración completa (studies `3bp_15m_stop_fix_v2` / `3bp_5m_stop_fix_v2`, mismos flags):

| | 15m | 5m |
|---|---|---|
| Trades | 1301 | 676 |
| Win rate | 38.8% | 32.4% |
| Profit factor | **1.20** | **1.41** |
| Expectancy | **+0.117R** | **+0.282R** |
| Max drawdown | 38.3R | 30.8R |

**El piso de ATR rescata el edge en los dos timeframes.** 5m queda con mejores métricas que 15m
(expectancy, PF, drawdown), pero con bastante menos señales (676 vs 1301) — una muestra más chica.

**Parámetros ganadores finales** (ambos con `wrb_multiplicador` pegado cerca del piso del rango de
búsqueda 1.0-4.0 otra vez — sigue sin investigarse por qué, ver pendientes):

| Campo | 15m | 5m |
|---|---|---|
| wrb_multiplicador | 1.047 | 1.018 |
| tolerancia_pct | 0.367 | 0.057 |
| n_invalidacion | 3 | 9 |
| target_r | 3.372 | 4.885 |
| ventana_inicio_barras | 7 | 8 |
| volumen_confirmado_mult | 3.550 | 3.094 |

### ¿15m, 5m, o los dos al mismo tiempo? — RESUELTO (2026-10-13)

Por trade (expectancy/PF), 5m seguía ganando a 15m incluso en una regeneración posterior con
eventos frescos (universo cacheado creció de ~495 a ~513 tickers entre el 02/10 y el 13/10, así
que los números cambian levemente respecto a la tabla de arriba — ruido de cache, no del fix):

| | 15m (n=1265) | 5m (n=630) |
|---|---|---|
| Win rate | 36.5% | 27.5% |
| Profit factor | 1.11 | 1.18 |
| Expectancy | +0.071R | **+0.138R** |

Pero lo que importa es el resultado de la CUENTA, no la expectancy por trade sola — se repitió la
misma simulación de cuenta compartida de la Ronda 3/4 ($300, riesgo≤1% sin apalancamiento, 3
posiciones, corte diario -3%, 231 días hábiles) con los eventos regenerados (cada timeframe con su
propio `volumen_confirmado_mult` óptimo, no el compartido de la config activa):

| Variante | Retorno | DD máx. real | Bootstrap DD p95 | P(perder) |
|---|---|---|---|---|
| 15m sola | **+70.8%** | 17.9% | 24.3% | 2% |
| 5m sola | +51.2% | 17.4% | 24.0% | 4% |
| 15m + 5m combinadas (3 slots compartidos) | +47.9% | 15.7% | **33.7%** | **9%** |
| 15m sola, riesgo ≤2%/trade | **+80.6%** | 20.8% | 28.1% | 2% |
| 5m sola, riesgo ≤2%/trade | +65.8% | 18.3% | 25.1% | 4% |

**Conclusión: 15m sigue siendo la mejor opción individual, y combinar ambos timeframes en la misma
cuenta sigue siendo la PEOR opción** — mismo resultado cualitativo que la Ronda 3/4, ahora
confirmado con datos post-fix. Al competir por los mismos 3 cupos solo entra el 46% de las señales
de 15m y el 72% de las de 5m (diluye calidad en vez de sumar); el drawdown máximo puntual de la
combinación (15.7%) parece el más bajo de la tabla, pero la cola de riesgo real (bootstrap p95
33.7%, P(perder)=9%) es la peor de todas. **Por qué 15m le gana a 5m en la cuenta pese a tener
menor expectancy por trade:** dispara el doble de señales (1265 vs 630) — compone más seguido, y
eso pesa más que la expectancy individual para el crecimiento de la cuenta. La mejor variante de
toda la tabla sigue siendo 15m sola con el doble de riesgo por trade.

**No operar 5m, no correr los dos timeframes a la vez.** La config activa (`scan_configs` id=12)
queda con el campo compartido `volumen_confirmado_mult` en el valor de 15m — correcto, ya no es una
decisión pendiente.

### Cierre (2026-10-13)

- Config activa actualizada con los parámetros ganadores de ambos timeframes (id=12).
- Eventos LIVE viejos (el trade de BZ, calculado con el bug) borrados de Turso.
- El vivo (`main.py`) ya usa el código corregido automáticamente — no hace falta ningún cambio
  adicional de wireo, el fix está en `Detector3BP` mismo, que alimenta tanto backtest como vivo.

---

## Ronda 7 (2026-10-13) — el indicador del manual ("r21ema"): la señal más fuerte encontrada

### La pregunta

Repasando el manual del curso (Live Traders, cap. "3 & 4 Bar Plays") en busca de algo que no se
hubiera probado todavía: en **todos** los gráficos de ejemplo de 3BP/4BP del manual aparece una
línea de EMA21 de referencia (etiquetada "r21ema" en las capturas), aunque no figura en la lista
numerada de criterios del patrón — es parte del método más amplio del curso ("primero sesgo de
tendencia en un timeframe mayor, después el patrón para el timing de entrada"), nunca antes
evaluado en este módulo (distinto del cruce EMA9/21 del clasificador de 6 criterios, probado sin
éxito en la Ronda 1.5).

### Validación (antes de tocar código)

Con los eventos post-fix ya cacheados (`eventos_3bp_{15m,5m}_postfix.pkl`, Ronda 6 paso 2) se trajo
la serie propia de cada ticker/timeframe (ya en `backtest_data/`, sin pegarle a Schwab) y se calculó
la EMA21 "as of" el momento de cada entrada:

- **"Precio > EMA21 ascendente" (el r21ema literal) no agrega nada sobre "precio > EMA21" solo** —
  la condición de pendiente no mejora el filtro, solo lo complica. Se descartó.
- **"Precio > EMA21" solo**, probado con split-half (dos mitades cronológicas del período, 15m y 5m
  por separado — 4 ventanas en total): las entradas con **precio ≤ EMA21 dan expectancy fuertemente
  negativa en las 4 ventanas** (-0.42R a -0.66R, profit factor 0.25-0.53). Es la señal más fuerte y
  consistente encontrada en todo el módulo hasta ahora — más que ATR% (Ronda 1.5), WRB ratio o tier
  (Ronda 5), que daban evidencia mixta o débil entre timeframes.

### Implementación

Confirmado el hallazgo, se implementó como filtro real, siguiendo el mismo patrón arquitectónico ya
usado para `bp34_solo_tier_confirmado` y `bp34_stop_min_pct`: el detector (`Detector3BP`) solo
**calcula y expone** el dato (`EventoPatron3BP.precio_sobre_ema21`, EMA21 propia del timeframe,
actualizada barra a barra de forma incremental O(1), igual que ya se hace con ATR14/volumen) — la
decisión de filtrar o no vive afuera, en `walker_3bp.py::_caminar_dia` (backtest) y
`main.py::_on_evento_3bp` (vivo), controlada por el nuevo campo `ScanConfig.
bp34_requiere_precio_sobre_ema21` (default `False`, no cambia el comportamiento de ninguna
calibración ya hecha hasta que se active explícitamente).

- `None` (menos de 21 barras de contexto vistas todavía) se trata igual que `False` al filtrar —
  "no se pudo confirmar que el precio esté sobre la EMA21" descarta la entrada, mismo criterio
  conservador que el resto del sistema (Regla 5 del clasificador de 6 criterios).
- Columna nueva `precio_sobre_ema21` en `bp34_eventos` (Turso), propagada tanto en backtest como en
  vivo, para poder auditar/reanalizar después sin tener que recalcularla.
- Flag `--requiere-ema21/--sin-ema21` agregado a `trading-scanner-optimize-3bp`.
- Tests nuevos en `test_pattern_3bp.py` (cálculo de la EMA21 incremental, los 3 estados
  `None`/`True`/`False`, y que no se resetea con el patrón) y `test_walker_3bp.py` (el filtro
  descarta `None` y conserva por default). Suite completa: 286 tests, 0 fallos.

### Recalibración con el filtro activado (2026-10-13/14) — resultado contradictorio con la validación

Se corrió `trading-scanner-optimize-3bp` para los dos timeframes con
`--requiere-ema21` activado (mismos flags que la Ronda 6 paso 2: `--slippage-bps 5 --stop-min-pct
0.6 --solo-confirmado --sesion-regular --ventana-entrada-min 90`, studies `3bp_15m_ema21_v1` /
`3bp_5m_ema21_v1`, 50 trials c/u, mismo universo ~515 tickers):

| | 15m sin filtro (Ronda 6) | 15m con filtro (Ronda 7) | 5m sin filtro (Ronda 6) | 5m con filtro (Ronda 7) |
|---|---|---|---|---|
| Trades | 1301 | **570** | 676 | **430** |
| Win rate | 38.8% | 38.6% | 32.4% | 34.0% |
| Profit factor | **1.20** | 1.17 | **1.41** | 1.33 |
| Expectancy | **+0.117R** | +0.099R | **+0.282R** | +0.229R |
| Max drawdown | 38.3R | 43.3R | 30.8R | **20.2R** |

**El filtro empeora (o en el mejor caso, no mejora) el resultado en los dos timeframes** —
contradice directamente la validación split-half de más arriba, que mostraba "precio ≤ EMA21" como
la señal más negativa de todo el módulo. 5m mejora el drawdown (30.8R → 20.2R) pero a costa de
expectancy y PF; 15m empeora en las tres métricas de calidad (PF, expectancy, drawdown) y además
pierde más de la mitad de las señales (1301 → 570).

**Por qué no implica que el hallazgo de la validación esté mal — son dos preguntas distintas:**
- La validación split-half midió "¿filtrar por EMA21 mejora los trades de la config GANADORA de la
  Ronda 6, sin tocar nada más?" — una pregunta de filtro aislado sobre parámetros fijos.
- Esta recalibración midió "¿cuál es la MEJOR combinación posible de `bp34_*` cuando el filtro es
  obligatorio?" — Optuna, forzado a cumplir el filtro, explora una región del espacio de parámetros
  distinta (`wrb_multiplicador` saltó de ~1.0-1.05 en la Ronda 6 a **3.54** en 15m con el filtro —
  un régimen de WRB mucho más exigente, no una variación menor) y con el mismo presupuesto de 50
  trials puede simplemente no haber encontrado tan bien el óptimo de esa región nueva como encontró
  el óptimo de la región sin filtro.
- Dicho de otro modo: no se probó "los mismos parámetros ganadores de la Ronda 6 + el filtro
  EMA21 encima", que es la comparación directamente equivalente a la validación split-half. Se
  probó "el mejor óptimo encontrable con el filtro obligatorio", que es una pregunta distinta y
  más dura de buscar (mismo presupuesto, espacio más restringido).

### Resolviendo la contradicción: el filtro post-hoc sobre los parámetros FIJOS de la Ronda 6

Se corrió la prueba que falta arriba: tomar los eventos ya generados con los parámetros ganadores
de la Ronda 6 (fijos, sin que Optuna los toque) y aplicar el filtro EMA21 como corte post-hoc —
exactamente la pregunta que mide la validación split-half, pooled sobre todo el período (no
dividido en mitades):

| | 15m TODOS (Ronda 6) | 15m + filtro EMA21 | 5m TODOS (Ronda 6) | 5m + filtro EMA21 |
|---|---|---|---|---|
| Trades | 1265 | 1129 | 630 | 546 |
| Win rate | 36.5% | **38.8%** | 27.5% | **29.3%** |
| Profit factor | 1.11 | **1.24** | 1.18 | **1.30** |
| Expectancy | +0.071R | **+0.140R** | +0.138R | **+0.221R** |
| Net profit | +89.6R | **+158.4R** | +87.2R | **+120.5R** |

**Confirma el hallazgo de la validación: el filtro, aplicado sobre la config que YA funciona, casi
duplica la expectancy en 15m (+0.071R → +0.140R) y la mejora un 60% en 5m (+0.138R → +0.221R), con
una pérdida de trades moderada (11% en 15m, 13% en 5m) — y el net profit SUBE en los dos a pesar de
operar menos.** La contradicción de la sección anterior no era del hallazgo: era de la metodología
de recalibración. Al forzar el filtro y dejar que Optuna buscara de nuevo todo el espacio de
`bp34_*`, terminó en una región distinta (`wrb_multiplicador` saltó a 3.54 en 15m) que con 50
trials no llegó a optimizarse tan bien como la región sin filtro — no porque el filtro sea malo,
sino porque la pregunta que esa búsqueda contestó ("mejor óptimo posible con el filtro obligatorio
desde cero") no es la misma que "¿mejora la config que ya tengo si le agrego este filtro encima?".

**Recomendación: activar `bp34_requiere_precio_sobre_ema21=True` en la config de producción,
MANTENIENDO los parámetros `bp34_*` ya vigentes de la Ronda 6** (no los de la recalibración Optuna
de esta ronda, que quedan descartados — peores en los dos timeframes). Los resultados de la
recalibración con el filtro forzado (`3bp_{15m,5m}_ema21_v1`, tabla de la sección anterior) no se
usan para nada productivo — quedan documentados solo como evidencia de la trampa metodológica.

### Simulación de cuenta de $300 — el efecto compone aún más fuerte a nivel cuenta

Mismo mecanismo de la Ronda 3/4/6 (cuenta compartida, 3 posiciones, riesgo≤1%, corte -3%/día,
bootstrap de 3000 muestras), ahora comparando con/sin el filtro EMA21 sobre los mismos eventos de
la tabla anterior:

| Variante | Retorno SIN filtro | Retorno CON filtro EMA21 | DD máx. SIN | DD máx. CON | P(perder) SIN → CON |
|---|---|---|---|---|---|
| 15m sola | +70.8% | **+126.6%** | 17.9% | **8.7%** | 2% → **0%** |
| 5m sola | +51.2% | **+85.7%** | 17.4% | **11.2%** | 4% → **0%** |
| 15m, riesgo≤2% | +80.6% | **+153.7%** | 20.8% | **9.8%** | 2% → **0%** |

**El efecto compone más fuerte a nivel cuenta que a nivel trade individual** — el filtro casi
duplica el retorno en las tres variantes y reduce el drawdown máximo a menos de la mitad en todas,
con `P(perder)` (bootstrap, 3000 muestras) bajando a 0% en las tres. Confirma con margen todavía
más amplio la decisión de activar el filtro.

### Cierre (2026-10-14)

- Config activa en Turso actualizada (id=13): `bp34_requiere_precio_sobre_ema21=True`, manteniendo
  intactos los `bp34_*` de la Ronda 6 (wrb_multiplicador 1.047/15m, 1.018/5m, y el resto).
- Código + tests + esta documentación commiteados y pusheados (`4e267ea`).

---

## Qué falta antes de operar esto en serio

1. ~~El vivo no filtra por horario todavía~~ — **resuelto** (`evento_en_ventana_permitida` en
   `main.py::_on_evento_3bp`, mismo código que usa el walker de backtest).
2. **`wrb_multiplicador` pegado al piso del rango de búsqueda (1.0-4.0) — ahora en los DOS
   timeframes, no solo 5m.** Tras el fix de stop (Ronda 6), 15m también convergió cerca de 1.0
   (1.047) además de 5m (1.018). Con dos calibraciones independientes dando el mismo resultado,
   esto ya no se puede descartar como ruido de una sola corrida — vale la pena ampliar el rango de
   búsqueda hacia abajo (ej. 0.5-4.0) en una próxima recalibración para ver si el óptimo real está
   fuera del rango actual.
3. **Revalidar contra `universo_real`** (tickers que salieron de verdad en los CSV de ToS
   guardados, no el universo curado de 470+ nombres ya sabidos como volátiles) — mismo caveat que
   arrastra el proyecto desde la calibración del clasificador de 6 criterios en agosto.
4. **Muestra de ~9-10 meses** (nov 2025 - ago 2026) — corta para conclusiones fuertes, un solo
   régimen de mercado. El "anualizado" es una extrapolación matemática de esos 9 meses, no una
   proyección real.
5. **Redondeo a acciones enteras: probado en la Ronda 4, efecto menor de lo temido** — solo 1% de
   las señales quedó descartada por no alcanzar ni para 1 acción con $300. Sigue sin modelarse la
   correlación entre posiciones abiertas el mismo día (varios tickers moviéndose juntos en un día
   de mercado direccional) — ese sesgo optimista sigue sin cuantificar.
6. **La variante "15m con riesgo ≤2%" no fue calibrada como tal** — es la misma señal de 15m con
   el dial de riesgo subido, no una recalibración de `bp34_*` pensada para ese nivel de riesgo.
7. **El edge no se sostiene fuera de acciones baratas (<$20)** — ver Ronda 4. Antes de operar con
   una cuenta más grande hace falta precargar un universo de nombres líquidos/caros de verdad y
   recalibrar `bp34_*` para ese régimen — no asumir que los parámetros de microcaps transfieren.
8. ~~Filtro por `tier="confirmado"` cuantificado pero no implementado~~ — **implementado 2026-09-29**
   (`bp34_solo_tier_confirmado`). Ya incluido en todas las recalibraciones de la Ronda 6.
9. ~~¿15m o 5m?~~ — **resuelto (2026-10-13)**: 15m, y no combinar — ver "¿15m, 5m, o los dos al
   mismo tiempo?" arriba. Combinar en la misma cuenta es la peor opción de todas las probadas.
10. **[Ronda 6] No se repitió la validación split-half (dos mitades del período) con los eventos
    post-fix** — sí se repitió la simulación de cuenta de $300 (ver arriba), pero no el chequeo de
    que el edge se sostiene en ambas mitades del rango temporal. Pendiente.
11. ~~`bp34_volumen_confirmado_mult` compartido entre timeframes, sin resolver del todo~~ —
    **resuelto**: queda en el valor de 15m, ya no es una decisión pendiente (ver punto 9).
12. ~~[Ronda 7] Filtro `bp34_requiere_precio_sobre_ema21` implementado pero sin recalibrar~~ —
    **resuelto y activado (2026-10-14)**: la recalibración con Optuna forzando el filtro dio peor
    resultado (trampa metodológica, ver Ronda 7), pero el filtro post-hoc sobre los `bp34_*` YA
    ganadores de la Ronda 6 casi duplica la expectancy y el retorno de la cuenta de $300 en los dos
    timeframes, con drawdown a menos de la mitad y `P(perder)`→0% en el bootstrap. Activado en la
    config de producción (id=13) manteniendo los `bp34_*` de la Ronda 6.
13. **[Pendiente futuro, no urgente] Cuando la cuenta crezca, evaluar escalar por DOS palancas
    independientes, no solo una** — tickers de mayor valor Y más posiciones simultáneas, testeadas
    por separado antes de combinarlas (para no tapar el efecto de una con el de la otra). Es un
    trigger futuro ("cuando crezca"), no algo a resolver antes de salir en vivo con el tamaño actual:
    - **Tickers de mayor valor:** ya cubierto por el punto 7 — el edge no está validado fuera de
      <$20, hace falta precargar un universo caro/líquido y recalibrar `bp34_*` para ese régimen.
    - **Más operaciones simultáneas:** más fácil de explorar de lo que parece, porque el límite de
      "3 posiciones" usado en las simulaciones de cuenta (Rondas 3/4/6/7) es un parámetro del script
      ad-hoc de simulación (`MAX_POS`, en el scratchpad, no versionado) — no algo enforced por
      `ScanConfig.posiciones_simultaneas_max` en un motor de ejecución real (ese motor no existe
      todavía, es Sprint 5). Evaluarlo es volver a correr el mismo script con `MAX_POS` más alto y
      mirar drawdown/cola de riesgo — no requiere tocar código de producción ni esperar Sprint 5.
    - **Nota regulatoria (2026-10-14):** FINRA eliminó la regla de Pattern Day Trader (y el piso de
      $25.000 de equity) el 4 de junio de 2026 (enmienda a la Rule 4210) — reemplazada por un mínimo
      estándar de cuenta de margen de ~$2.000 (depende del broker) y un framework de margen
      intradiario en tiempo real, sin límite de cantidad de day trades por período. En cuenta cash
      (sin margen) sigue aplicando el settlement T+1 y el riesgo de *good faith violation* al
      reciclar capital intradía (3 GFV en 12 meses → restricción a fondos liquidados por 90 días en
      Schwab) — relevante para el diseño de ejecución futura (Sprint 5), no para el scanner en sí.

## Scripts usados (no versionados, en el scratchpad de la sesión — no en el repo)

Todo el análisis de correlación, cuantificación de costos y simulación de cuenta se hizo con
scripts ad-hoc fuera del repo (correlacion_3bp_*.py, cuantificar_filtro_atr.py, costos_stop.py,
simular_cuenta*.py). Si se decide formalizar alguno de estos análisis como herramienta reusable
(en particular la simulación de cuenta — sería el análogo de `backtest/simulator.py` pero a nivel
de cartera, no de trade individual), es trabajo nuevo, no algo ya hecho en el repo.
