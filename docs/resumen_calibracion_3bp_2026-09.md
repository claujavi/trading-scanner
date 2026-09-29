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

**Status: identificado, no implementado como filtro real** (`volumen_confirmado_mult` sigue siendo
puramente informativo en el detector, no descarta nada) — candidato fuerte para una próxima
recalibración que incluya la opción de filtrar por tier, o simplemente aplicarlo como post-filtro
manual sobre las señales que ya salen del sistema.

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
5. **Redondeo a acciones enteras: probado en la Ronda 4, efecto menor de lo temido** — solo 1% de
   las señales quedó descartada por no alcanzar ni para 1 acción con $300. Sigue sin modelarse la
   correlación entre posiciones abiertas el mismo día (varios tickers moviéndose juntos en un día
   de mercado direccional) — ese sesgo optimista sigue sin cuantificar.
6. **La variante "15m con riesgo ≤2%" no fue calibrada como tal** — es la misma señal de 15m con
   el dial de riesgo subido, no una recalibración de `bp34_*` pensada para ese nivel de riesgo.
7. **El edge no se sostiene fuera de acciones baratas (<$20)** — ver Ronda 4. Antes de operar con
   una cuenta más grande hace falta precargar un universo de nombres líquidos/caros de verdad y
   recalibrar `bp34_*` para ese régimen — no asumir que los parámetros de microcaps transfieren.
8. **Filtro por `tier="confirmado"` cuantificado pero no implementado** (Ronda 5) — mejora retorno
   y drawdown a la vez en la cuenta de $300 (15m). Candidato fuerte para la próxima iteración.

## Scripts usados (no versionados, en el scratchpad de la sesión — no en el repo)

Todo el análisis de correlación, cuantificación de costos y simulación de cuenta se hizo con
scripts ad-hoc fuera del repo (correlacion_3bp_*.py, cuantificar_filtro_atr.py, costos_stop.py,
simular_cuenta*.py). Si se decide formalizar alguno de estos análisis como herramienta reusable
(en particular la simulación de cuenta — sería el análogo de `backtest/simulator.py` pero a nivel
de cartera, no de trade individual), es trabajo nuevo, no algo ya hecho en el repo.
