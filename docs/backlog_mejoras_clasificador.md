# Backlog: mejoras al clasificador de 6 criterios

Ideas que surgieron comparando `estrategia_actual.md` contra el resumen del curso Live Traders,
revisadas y repriorizadas después de contrastarlas contra el código real del proyecto (sesión en
VS Code). Ninguna está decidida para implementación salvo donde se marca explícitamente como
bloqueante — quedan anotadas para no perderlas, independientes del trabajo del módulo 3BP/4BP.

`Resumen Live Traders - Professional Trading Strategies.md` está subido en el proyecto (`docs/`)
— fuente completa de contexto. Las secciones "Notas para nuestra estrategia" al final de cada
parte tienen más detalle y más candidatos que no llegaron a esta lista priorizada.

---

## ⚠️ Excepción a la prioridad por esfuerzo: money management real

El punto 4 de esta lista queda último en la cola de "qué se codea primero" porque es el de mayor
alcance técnico. Pero no es un backlog más entre otros cinco: es un **bloqueante duro para
cualquier paso a producción real**, sin importar en qué orden se trabajen los demás puntos.
"Preservación de capital por encima de todo" es el principio no negociable del proyecto, y hoy
—según lo confirmado en el código— no hay ningún límite de riesgo real funcionando. Mientras el
sistema siga en modo análisis sin ejecutar nada, el costo de tenerlo pendiente es bajo. Si en
algún momento se evalúa pasar a producción, este punto no se puede saltear.

---

## Prioridad 1 — Estructura de pivotes (reemplaza el bit binario de SMA200) + EMA200 de referencia ✅ implementado (live) — ⚠️ ver gap de backtest

Hoy `criterio_sma200` es literalmente un bit: `(1.0, 0.0) si sobre_sma200 else (0.0, 1.0)` — la
señal más pobre de las 6. La estructura de pivotes (HPH/HPL para tendencia alcista, LPH/LPL para
bajista) es una función pura sobre la serie de precios, testeable en aislado, sin datos nuevos
que no se descarguen ya (mismas velas diarias/4h). Buen ratio esfuerzo/valor — es una
**modificación del criterio 5 existente, no un criterio nuevo**, no toca el espacio de pesos del
optimizador.

El ciclo de 4 etapas de Wyckoff (acumulación/tendencia/distribución/tendencia bajista) queda en
el radar pero no entra en esta primera pasada — mezcla rango, volumen y tendencia con juicio
cualitativo, más caro de operacionalizar bien.

La EMA 200 se calcula sobre **diario** (no 60' — el sistema no descarga ese timeframe hoy),
puramente informativa, no entra al score. Ver `docs/spec_criterio_pivotes.md` sección 6.

**Implementación:** `engine/pivots.py::detect_estructura_pivotes()` (fractal `L=3` a cada lado,
tolerancia `0.5×ATR14` para filtrar ruido, mínimo 2 pivotes consecutivos — los 3 parámetros son
campos de `ScanConfig`, ninguno tocado por el optimizador). Caso INDETERMINADA → `None` (criterio
no calculable, Regla 2 — sin fallback al bit binario, decisión confirmada explícitamente).
`criteria.py::criterio_sma200` cambia de firma (recibe `estructura_pivotes: Optional[str]` en vez
de `sobre_sma200: bool`). `sobre_sma200` se mantiene como campo informativo (ya no alimenta el
score). Wireado en el pipeline en vivo (`signals.py`, `pipeline.py`) y en el stream
(`market_data_cache.py`) — persistido en Turso vía `ALTER TABLE` tolerante a fallos (no hay
sistema de migraciones en el proyecto). `evaluator_version` bumpeado a 1.3.0. Tests en
`tests/unit/test_pivots.py` (20 casos) y `tests/unit/test_criteria_sma200.py`.

**⚠️ Gap detectado durante la implementación, no cerrado en esta pasada:** `backtest/runner.py`
tiene su propio camino vectorizado (`_serie_sobre_ma`, `_valor_asof`, ver el trabajo de
performance documentado en `resumen_optimizador_2026-07.md`) que **no fue actualizado** — no
calcula `estructura_pivotes`, así que en todo backtest y en el optimizador este criterio queda
permanentemente en `None` (no calculable) hasta que se vectorice ahí también. No rompe nada (Regla
2: no penaliza, `score_max_posible` baja de 6.0 a 5.0 en vez de fallar), pero el criterio 5 no
aporta nada en calibración hasta cerrar este punto — vectorizar pivotes es más complejo que
EMA/SMA/ATR porque un pivote requiere `L` barras *posteriores* para confirmarse, así que el
`_valor_asof` no puede ser un simple lookup por fecha: hace falta trackear, por cada pivote
precalculado, su fecha de *confirmación* (no su fecha propia) y filtrar por esa fecha al hacer el
corte "as of ayer" en cada día evaluado.

**Status:** hecho en el pipeline en vivo y el stream. Pendiente: vectorizar en `backtest/runner.py`
antes de que el optimizador pueda calibrar sobre esta señal — decisión explícita de dejarlo para
después, ver Prioridad 1.5 más abajo (no es un pendiente flotante, queda trackeado).

---

## Prioridad 2 — Escalado por precio del filtro de variación diaria ✅ implementado

Hoy `variacion_diaria_min_pct` es un umbral plano (2%) sin importar si la acción cotiza a $6 o a
$60 — no distingue que un gap grande porcentualmente en una acción barata tolera más que el mismo
% en una cara. Fix barato y separable del sistema completo de gap rating: es un ajuste al filtro
de entrada (paso 0), no un criterio scoreado, no toca pesos.

**Implementación:** `evaluator._umbral_variacion_diaria(precio, config)` — a
`variacion_diaria_precio_referencia` (default $20) aplica `variacion_diaria_min_pct` tal cual; para
otros precios escala por `precio_referencia / precio`, acotado entre `variacion_diaria_escala_min`
(0.5) y `variacion_diaria_escala_max` (2.5). Ejemplo: acción de $6 → umbral efectivo 5.0% (antes
2.0%); acción de $200 → umbral efectivo 1.0%. 3 campos nuevos en `ScanConfig`, ninguno tocado por
el optimizador (`search_space.py` no los referencia). Tests en
`tests/unit/test_evaluator_filtro_variacion_diaria.py`.

**Status:** hecho.

---

## Prioridad 3 — RelVol tipificado (Igniting/Ending/Resting)

Distingue "volumen que inicia un movimiento" (≥2x promedio) de "volumen que lo agota" (≥2x tras
un tramo extendido) de "volumen que solo sostiene continuación" (~0.5x) — hoy `relvol` es un
escalar calculado una sola vez sobre velas diarias (`calc_relvol`), no una lectura de secuencia
de barras. Para tipificarlo hace falta mirar varias velas consecutivas y su dirección, lo cual no
encaja en el criterio estático actual — encaja en el motor de eventos del stream
(`market_data_cache.py`), que ya trackea velas de 5m bucketeadas y detecta eventos (cruce EMA,
nuevo máx/mín). Es la pieza correcta del sistema, pero implica trabajo sobre el stream, no un
ajuste de umbral. Es una **modificación del criterio 3 existente**, no toca pesos.

**Status:** tercero — valioso pero el más caro de los tres primeros.

---

## Prioridad 3.5 — SWING se simula igual que DAY (cierre forzado el mismo día)

**Hallazgo (2026-08-04), al revisar trade por trade el resultado de la re-corrida del optimizador
post-fix** (`docs/resumen_optimizador_2026-08.md`, trial ganador `curado_v3_fix_dia`): de los 15
trades simulados, varios clasificados `SWING` (CVE, BILI, STM, NOK, EQNR, GIS, TEVA, GMAB, CPRT,
NKE) se simularon **exactamente igual** que los `DAY` — entrada en la apertura, cierre forzado a
las 15:55 ET **del mismo día**, sin ninguna posibilidad de sostener la posición más de una sesión.
`backtest/simulator.py::simular()` recibe siempre `velas_dia = filter_range(df_5m_full, fecha,
fecha)` (ver `runner.py::_evaluar_dia_desde_cache`) — un solo día, sin importar la clasificación.
Conceptualmente un SWING debería sostenerse varios días; hoy el sistema nunca prueba eso, ni en
backtest ni (por construcción, ya que el simulador es el mismo) en cómo se gestionaría en vivo.

**Decisión tomada (2026-08-04), para implementar:**
- Las posiciones clasificadas `SWING` ganan un corte programado propio: **15 días hábiles** (~3
  semanas), en vez del cierre forzado al mismo día que hoy comparten con `DAY`. Constante fija,
  **no** un campo que optimice Optuna — sin datos reales todavía para calibrar el número, y
  agregar otra variable libre al espacio de búsqueda repite el mismo riesgo de sobreajuste que ya
  motivó no tocar los `peso_*`.
- Mientras la posición sigue abierta, se reusa el trailing stop que ya existe (
  `trailing_activacion_r` mueve a breakeven, `trailing_lock_r` asegura ganancia) — protege
  resultado sin necesitar una máquina de estados nueva.
- **No implica reescribir el simulador como caminador de múltiples días completo** — alcanza con
  extender `runner.py`/`simulator.py` para que, cuando la clasificación sea `SWING`, la ventana de
  velas evaluada cubra hasta 15 días hábiles en vez de 1, aplicando el mismo criterio de cierre
  forzado (target/stop/trailing) sobre esa ventana más ancha.

**Pendiente para más adelante, documentado a propósito para no perderlo:** una versión más
inteligente del corte (cerrar según qué tan lejos se movió el precio, no un N fijo de días) exige
una infraestructura de posición con estado persistente entre días — el mismo tipo de trabajo que
el walker del paso 4 de `spec_modulo_3bp_4bp.md` (caminar vela por vela con estado, en vez de "un
día = un contexto" como hace `runner.py` hoy). Son proyectos separados —el walker del paso 4 es
específicamente para backtestear el patrón 3BP/4BP, no la gestión de posición SWING del
clasificador de 6 criterios— pero comparten la misma idea de fondo, y si en algún momento se
construye esa infraestructura general, tiene sentido revisar si sirve para ambos casos.

**Status:** ✅ implementado (2026-08-04). `simulator.py::simular()` gana `fecha_limite_cierre`
opcional (default `None` = comportamiento DAY sin cambios); `_truncar_a_cierre_forzado()` corta en
ese día si se pasa, en vez del día de la primera vela — deja pasar los días intermedios completos.
`runner.py::_sumar_dias_habiles()` (nuevo) calcula la fecha límite; `_evaluar_dia_desde_cache()`
arma la ventana de velas 5m según la clasificación (`fecha` a `fecha` para DAY, `fecha` a `fecha +
14 días hábiles` para SWING) y pasa `fecha_limite_cierre` solo en el caso SWING.
`_evaluar_ticker_para_dias()` extiende el pedido de velas 5m (`fin_5m`) más allá del último día
evaluado, para que haya datos disponibles con los que sostener un SWING generado cerca del final
del rango pedido. 8 tests nuevos (`tests/unit/test_simulator.py`,
`tests/unit/test_runner_batch_por_ticker.py`) — target/stop cruzando días, cierre en el último día
(no el primero), `_sumar_dias_habiles` con fin de semana, y el fetch extendido de 5m. Pendiente:
re-correr el optimizador/backtest con este fix para ver cómo cambian los números de
`docs/resumen_optimizador_2026-08.md` (probablemente mejoran para SWING).

**Seguimiento (2026-08-04) — stop/target acotados, no rediseñados:** se discutió si redefinir el
stop directamente en dólares fijos según el capital (ej. "stop = entrada − $2" con $200 y 1% de
riesgo). Se descartó: el precio del stop es una decisión de mercado/volatilidad (ATR), independiente
del capital — lo que sí depende del capital es la **cantidad de acciones** a comprar dado ese stop
(`CDAD = riesgo_$ / (entrada − stop)`), que es exactamente el gap de money management ya anotado
en la Prioridad 4 más abajo, con una fórmula de referencia concreta provista por el trader (ver esa
sección). En cambio, se acotó `stop_atr_multiplicador` en `optimizer/search_space.py` de `0.8-3.0`
a `1.0-2.0` (centrado en el default 1.5, la regla R2 de `spec_modulo_3bp_4bp.md`) — el rango viejo
permitía a Optuna encontrar 2.74 como "mejor" stop, que combinado con `rr_target` alto ponía el
target a ~10x ATR de distancia (inalcanzable en la ventana de simulación, target desactivado de
facto). `rr_target` queda sin tocar (1.2-4.0) — decisión explícita de dejar que Optuna siga
explorando libremente qué R rinde mejor, ahora con un stop realista de base.

---

## Prioridad 4 — Money management real (ver advertencia arriba)

Hallazgo de la revisión de código: `perdida_maxima_diaria_pct`, `posiciones_simultaneas_max` y
`riesgo_por_operacion_pct` ya existen como campos en `ScanConfig`, pero no los usa nadie — no
aparecen en el evaluador, ni en el pipeline, ni en el simulador de backtest. Son campos
declarados y muertos. **Corrección a una nota anterior de este backlog:** se asumía que el R4
(3% diario) ya estaba enforced — no es así, en la práctica hoy no hay ningún límite de riesgo
real funcionando.

Además, el simulador de backtest evalúa cada señal de forma independiente (por ticker/día), sin
estado acumulado de R en el día — implementar el esquema en capas del curso (2R exposición
simultánea, 3R diario, 9R semanal, 12R mensual con reducción a medio lote) requiere rearmar el
backtest para que sea secuencial/con estado dentro del día, no solo evaluar señal por señal.

Los puntos "límites en capas" y "protocolo simétrico de toma de ganancias" (antes ítems separados
4 y 5) se unen en un solo trabajo porque ambos necesitan la misma infraestructura que hoy no
existe: tracking real de R acumulado. Secuencia sugerida: primero conectar lo que ya existe pero
está muerto (simple), después decidir si conviene el esquema en capas del curso o uno propio más
simple, y recién ahí sumar el protocolo de ganancias.

**Fórmula de referencia para position sizing (aportada por el trader, 2026-08-04)** — así calculaba
esto manualmente antes del sistema, sirve como base concreta cuando se implemente:

```
stop_dist_teorico = entrada − stop          # entrada y stop ya decididos (técnico/ATR), no acá
cantidad_acciones = round(riesgo_$ / stop_dist_teorico)
capital_usado     = entrada × cantidad_acciones          # informativo
r_efectivo_$      = riesgo_$ / cantidad_acciones          # ajustado por el redondeo de acciones
target(nR)        = entrada + nR × r_efectivo_$            # nR = 1, 1.5, 2, 2.5, 3...
```

Ejemplo verificado (capital $300, riesgo fijo $3/trade ≈ 1%): ticker con entrada $2.70, stop $2.44
→ `cantidad_acciones = round(3 / 0.26) = 12`, `capital_usado = $32.40`, `r_efectivo_$ = 3/12 = $0.25`
→ target 2R = `2.70 + 2×0.25 = $3.20`. El detalle importante: los targets usan `r_efectivo_$`
(ajustado por el redondeo de `cantidad_acciones`), no la distancia técnica cruda — así la pérdida
real, si salta el stop, queda lo más cerca posible de `riesgo_$` exacto pese al redondeo.

**Status:** el de mayor alcance técnico de la lista — y el único con carácter de bloqueante para
producción, no de mejora opcional.

---

## Prioridad 5 — Gap rating completo (Nivel 1/2/3, con matices +/-)

Separado del criterio de catalizador (que sigue midiendo "¿hay un evento programado en 24h?" —
el "por qué"), porque el gap rating mide algo distinto: "¿qué tan bien se ve técnicamente el gap
de hoy?" (sobre qué pivote, hacia qué vacío, shock value) — el "cómo". Fusionarlos mezclaría dos
preguntas distintas.

Si se implementa, debería seguir la misma lógica arquitectónica que el módulo 3BP/4BP: **módulo
separado y desacoplado del score de 6 criterios**, no un 7mo criterio sumado al mismo
optimizador. Así se evita ampliar el espacio de parámetros del optimizador antes de acumular los
60+ días de datos reales que ya exige la regla de no tocar pesos — la misma razón por la que 3BP
no se mezcla con el score.

**Status:** más adelante, como módulo aparte, no como parche al criterio 2.

---

## Prioridad 1.5 — Vectorizar runner.py para incluir el criterio de pivotes en el backtest/optimizador

Decisión explícita (no un pendiente flotante — mismo tipo de gap que los campos muertos de
money management que ya encontramos una vez, así que esta vez queda anotado desde el día uno):
hoy el criterio de estructura de pivotes (Prioridad 1) corre en vivo y en el stream, pero
**no** en `backtest/runner.py`, que tiene su propio camino vectorizado (`_serie_sobre_ma`,
`_valor_asof`) sin actualizar. Resultado: en todo backtest y en el optimizador, este criterio
queda permanentemente `None` (no calculable, `score_max_posible` baja de 6.0 a 5.0) — no rompe
nada, pero el criterio 5 no aporta nada en calibración hasta cerrar este punto.

Se dejó para después conscientemente: no bloquea nada que hoy dependa de esa calibración — el
backtest histórico completo ya está marcado en `estrategia_actual.md` como preliminar
("hipótesis direccional, no calibración final", 7 trades de muestra en el run del optimizador de
julio 2026).

Más difícil que vectorizar EMA/SMA/ATR (que son consultas "as of" triviales por fecha): un
pivote necesita `L` barras *posteriores* para confirmarse, así que `_valor_asof` no alcanza con
un lookup simple — hace falta trackear, por cada pivote precalculado, su fecha de
**confirmación** (no su fecha propia) y filtrar por esa fecha al recortar "como se veía ayer" en
cada día evaluado.

**Status:** evaluar junto con la Prioridad 3 (RelVol tipificado) — ambas tocan el motor de
stream/backtest, tiene sentido revisarlas en la misma pasada en vez de por separado.

---

## Notas

- Los puntos 1 y 2 ya están codeados (ver status de cada uno arriba) — 1 con el gap de backtest
  documentado en la Prioridad 1.5. Los puntos 1, 2 y 3 modifican criterios/filtros existentes y
  no tocan pesos del optimizador. El punto 5, si se implementa, debe hacerlo como módulo
  desacoplado por el mismo motivo. El punto 4 es la excepción de alcance y de obligatoriedad —
  ver advertencia al inicio.
- No bloquean el desarrollo del módulo 3BP/4BP (`spec_modulo_3bp_4bp.md`), que sigue su propio
  camino en paralelo.
