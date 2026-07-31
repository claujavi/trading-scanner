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
