# Spec: Módulo de detección 3BP/4BP (intraday)

Documento de traspaso de diseño → implementación. Surge de una charla de estrategia comparando
`estrategia_actual.md` (sistema en producción/desarrollo) contra el resumen del curso Live Traders
("Professional Trading Strategies"). El objetivo de esta fase es sumar un módulo de detección de
patrones 3/4 Bar Play (3BP/4BP) como capa de *timing de entrada*, separado del clasificador de
6 criterios que ya existe.

---

## Contexto necesario

- `Resumen Live Traders - Professional Trading Strategies.md` está subido en el proyecto
  (`docs/`) — es la fuente completa del curso usada como referencia para el diseño de este
  módulo, con más detalle que lo resumido acá.
- El sistema hoy clasifica candidatos (ya filtrados a mano en ToS Stock Hacker + Finviz) como
  DAY, SWING o descarte, usando 6 criterios ponderados con score (ver `estrategia_actual.md`).
- Tiene 3 modos de gestión de posición configurables: `FIXED_RR`, `TRAILING_EOD`, `PARTIAL_SCALE`.
  Default actual: `FIXED_RR`.
- R2 (regla de stop): el stop final es el **mayor** entre ATR14×1.5 y el nivel técnico más
  cercano y lógico. Esta regla se reutiliza tal cual para 3BP, solo cambia el insumo de "nivel
  técnico" (ver más abajo).
- El sistema no ejecuta órdenes — es de análisis/clasificación. Roadmap declarado: no pasar a
  producción real de ningún componente nuevo hasta acumular datos suficientes en modo shadow.

---

## Objetivo de esta fase

Construir un módulo independiente que detecte patrones **+3BP / +4BP alcistas** en tiempo real
sobre velas intradía (5m/15m), para el universo de candidatos que ya pasó el filtro base del día
— sin depender de si el clasificador de 6 criterios los etiquetó como DAY o SWING. El módulo no
reemplaza ni se mezcla con el score existente: es una señal de timing paralela.

---

## ⚠️ Corrección post-análisis de viabilidad: se descarta 2m para v1

Al revisar la implementación contra el código real (sesión en VS Code, 2026-07-31) apareció un
bloqueante que la versión original de esta spec no detectó.

**Qué se asumió mal:** que 2m era descargable de Schwab tal cual, igual que 5m/15m, y que por eso
era una capa "barata" de agregar por encima de los timeframes que ya usa el clasificador.

**Por qué estaba mal:** la API de Schwab (vía `schwab-py`) solo expone frecuencias de 1, 5, 10, 15
y 30 minutos —

```python
>>> [str(f) for f in schwab.client.Client.PriceHistory.Frequency]
['Frequency.EVERY_MINUTE', 'Frequency.EVERY_FIVE_MINUTES', 'Frequency.EVERY_TEN_MINUTES',
 'Frequency.EVERY_FIFTEEN_MINUTES', 'Frequency.EVERY_THIRTY_MINUTES']
```

no existe "cada 2 minutos". Conseguir velas de 2m requeriría traer velas de **1 minuto**
(que el sistema tampoco soporta hoy — `schwab_history.py`/`history_cache.py` solo conocen
`"5m", "15m", "4h", "d"`) y bucketearlas a 2m a mano, tanto para el stream en vivo como para el
historial de backtest. Es decir: 2m no era una capa liviana sobre 5m/15m, era **1m con un paso
extra encima** — exactamente lo mismo (ruido operacional, retención de historia intradía sin
confirmar) que ya había descartado 1m en la versión original de esta spec, ahora aplicado
también a 2m, invirtiendo la razón original por la que se había elegido 2m en vez de 1m.

**Decisión final:** v1 del módulo corre **solo en 5m y 15m** — los mismos timeframes que ya usa
el clasificador de 6 criterios, sin agregar ningún timeframe nuevo ni soporte de 1m/2m. Ver
"Fuera de alcance" más abajo (1m y 2m quedan unificados en un solo ítem pendiente de
infraestructura, no como dos pendientes separados). Consecuencia práctica: los parámetros por
timeframe de la sección 9 bajan de 3 perfiles (2m/5m/15m) a 2 (5m/15m) — 8 campos en total (4
parámetros × 2 timeframes), y quedan como **campos planos en `ScanConfig`**, mismo patrón que el
escalado de precio del filtro de variación diaria (`docs/backlog_mejoras_clasificador.md`,
Prioridad 2) — no hace falta una estructura anidada con solo 2 timeframes.

---

## Alcance de esta fase (in scope)

### 1. Universo y timeframes

- Corre sobre **todas** las candidatas que pasaron el filtro de entrada (paso 0: precio, volumen
  promedio, ATR% mínimo, RelVol mínimo, variación diaria mínima, spread) — **no** filtrado por el
  criterio de catalizador ni por la clasificación DAY/SWING del scorer.
- Timeframes: **5m y 15m** — los mismos que ya usa el clasificador de 6 criterios (misma
  convención de "timeframes de identificación de setup"), sin agregar ningún timeframe nuevo. 2m
  y 1m quedan fuera de esta fase (ver corrección al inicio del documento y "Fuera de alcance") —
  no son descargables/derivables de Schwab sin construir soporte de 1m + resampleo primero, y el
  mismo argumento que descartaba 1m (ruido operacional, retención de historia intradía sin
  confirmar) aplica igual a 2m. Evaluado en tiempo real contra el stream (mismo mecanismo que ya
  usa el sistema para reevaluar en vivo).
- **Cada timeframe (5m, 15m) corre como detector independiente**, con su propio perfil de
  parámetros (multiplicador WRB, tolerancia, N de invalidación, target R) — no se comparte un
  solo perfil entre los dos, porque la volatilidad por barra difiere entre 5m y 15m.
- Solo direcciones **alcistas** (+3BP / +4BP). No se implementan variantes bajistas (-3BP/-4BP)
  en esta fase — ver "Fuera de alcance".

### 2. Definición mecánica del patrón

- **Rango de referencia:** ATR14 del timeframe evaluado (reutilizar el que ya calcula el
  sistema, no introducir un segundo concepto de "rango promedio").
- **Barra 1 (WRB):** rango (high−low) ≥ *k* × ATR14. Punto de partida propuesto: k = 2 (a
  calibrar). Debe iniciar un movimiento nuevo: las barras previas (ventana a definir, ej. 3-5
  barras) no deben tener ese rango — evita marcar como "barra 1" una vela grande en medio de una
  tendencia ya extendida.
- **Barra 2 (y 3 para 4BP) — definición numérica sin ambigüedad:**
  Sea barra 1 con mínimo `m1`, máximo `M1` y rango `R1 = M1 − m1`. Punto medio:
  `pm = m1 + 0.5 × R1`.
  - **Condición de posición:** el **mínimo** de cada barra del grupo (barra 2, y barra 3 si
    aplica) debe ser `≥ pm` — la barra se apoya en la mitad superior del rango de la barra 1, sin
    bajar de la mitad. Esto **no** significa que la barra quede por encima de la barra 1 entera
    (eso ya la convertiría en la barra gatillo) — sigue dentro o pegada al rango de la barra 1,
    solo que en su mitad superior. Ejemplo: barra 1 con mínimo 2 y máximo 10 (rango 8) → punto
    medio = 2 + 4 = 6 → el mínimo de la barra 2 tiene que ser ≥ 6.
  - **Condición de techo:** el **máximo** de cada barra del grupo debe ser `≤ M1` (aprox., con la
    tolerancia de abajo) — si una barra del grupo ya supera el máximo de la barra 1, deja de ser
    una barra de consolidación y pasa a ser la barra gatillo.
  - **Condición entre barras del grupo:** los máximos de las barras del grupo entre sí deben ser
    relativamente iguales — ese nivel de máximos iguales es el que define la resistencia que
    rompe la barra gatillo. Tolerancia propuesta: ±20-30% del rango de la barra 1 (a calibrar).
  - El color de estas barras no importa.
- **Resolución dinámica 3BP vs 4BP:** no se decide de antemano. Si la barra siguiente a la barra 2
  rompe el máximo del grupo → dispara como 3BP. Si en cambio se mantiene dentro de tolerancia →
  pasa a ser la barra 3, y el patrón queda esperando una barra 4 que rompa.
- **Barra gatillo:** rompe el máximo del grupo (2 o 3 barras) → dispara entrada.
- **Stop:** mínimo del grupo de barras (2, o 2-3). Se alimenta como "nivel técnico" a la regla R2
  ya existente: `stop = max(ATR14 × 1.5, mínimo estructural del patrón)`. No es una regla nueva,
  es un insumo nuevo a la regla que ya existe.
- **Confirmación de volumen (opcional, no bloqueante):** volumen ≥ 2× el promedio en la barra
  gatillo → tier "confirmado". Sin eso → tier "sin confirmar". Ambos se registran, ninguno se
  descarta a priori.

### 3. Máquina de estados

Por ticker + timeframe:

- **Estado 0 — Sin patrón.**
- **Estado 1 — Posible 3BP:** se detectó la barra 1 (WRB). Emite aviso temprano, no ejecutable.
- **Estado 2 — Esperando entrada:** barra(s) 2(-3) confirmadas dentro de tolerancia. Patrón
  válido, falta la ruptura.
- **Estado 3 — Entrada:** barra gatillo rompe el máximo. Calcula entry/stop, dispara señal.
- **Invalidación (vuelve a Estado 0):** (a) una barra cierra por debajo del mínimo de la barra 1
  (rompe la estructura), o (b) pasan más de *N* barras sin ruptura desde que se alcanzó Estado 2
  (*N* a definir con backtest, sin propuesta de partida todavía).

### 4. Salida del módulo (contrato de datos)

Por evento: ticker, timeframe, estado, dirección (solo `+` en esta fase), entry, stop, timestamp
de detección, tier de confirmación (con/sin volumen), snapshot completo de los parámetros de
configuración usados (k del WRB, tolerancia, ventana de referencia, N de invalidación) — mismo
principio de reproducibilidad total que ya aplica el resto del sistema.

### 5. Relación con el sistema existente

- **No se mezcla con el score de 6 criterios.** Queda como dato adicional visible en el output
  diario, no como filtro ni como sumador de puntos.
- **No se cruza con la clasificación DAY/SWING** para decidir si corre o no — ver punto 1.
- **Gestión de posición:** modo `FIXED_RR`, mismo que el default general del sistema — pero con
  un **perfil de parámetros separado** del que usa el día/swing genérico basado en catalizador:
  - Stop: fórmula R2 ya existente, alimentada con el nivel técnico del patrón (punto 2).
  - Target (múltiplo de R): debe ser un parámetro distinto y probablemente más alto que el del
    perfil genérico, dado que el stop de 3BP tiende a ser más ajustado (mejor R:R estructural).
    **No se definió un número final en la charla** — dejar como config separada a calibrar en
    backtest, no reusar el valor del perfil genérico.
  - Los dos perfiles (genérico y 3BP) se calibran por separado en el optimizador, no en la misma
    corrida — mismo criterio de no mezclar con el score.

### 6. Modo shadow / registro de operaciones

- No ejecuta órdenes. Al llegar a Estado 3, registra la operación como si se hubiese tomado:
  entry, stop, target (según el perfil FIXED_RR de 3BP).
- Sigue el precio real post-señal y guarda el resultado: tocó stop, tocó target, o llegó al cierre
  forzado del día sin definir (ver punto 7).
- Guardar todos los datos de R:R del recorrido (no solo el resultado final) — MFE/MAE, R final,
  tiempo en el trade.
- Objetivo explícito: acumular volumen de datos en modo shadow antes de evaluar cualquier paso a
  producción real. El umbral de 60+ días de datos (mismo criterio que ya aplica el sistema para
  no tocar pesos) es condición **necesaria pero no suficiente** — el paso a producción real
  requiere además aprobación explícita del trader, no es automático por volumen de datos. Esta
  lógica de aprobación no está codeada todavía, queda como principio a implementar.

### 7. Fix de gap general del sistema (no exclusivo de 3BP) ✅ implementado

**Corrección respecto a la charla original:** se asumía que `TRAILING_EOD` ya tenía el cierre
forzado a las 15:55 ET implementado y que solo faltaba extenderlo a `FIXED_RR`/`PARTIAL_SCALE`.
Al revisar `backtest/simulator.py` no había **ningún** cierre forzado explícito en ninguno de los
3 modos — los tres caían al último valor de `velas_dia` sin ningún chequeo de horario. Peor
todavía: se confirmó sobre datos reales cacheados (`backtest_data/AAL/5m/2026/01.parquet`) que
`velas_dia` para "un día" llega a cubrir velas hasta las **23:20 hora NY** — muy por fuera de
cualquier sesión de trading real, no solo un poco después del cierre.

**Fix implementado:** `simulator.py::_truncar_a_cierre_forzado()` corta las velas a las 15:55 NY
del día de la vela de entrada, aplicado **una sola vez en `simular()`** antes de despachar a
cualquiera de los 3 modos — no duplicado en cada uno. Como los 3 modos ya caían naturalmente al
último valor disponible cuando no se tocaba stop/target, truncar la serie de entrada alcanza para
que los 3 respeten el cierre forzado sin tocar su lógica interna. Timestamps de Schwab son naive
pero representan un instante UTC (no hora NY) — se convierte explícitamente antes de comparar.
Corte por fecha+hora completa (no solo "hora del día ≤ 15:55"), para no re-admitir por error la
madrugada del día siguiente si la serie llegara a cruzar medianoche. Tests en
`tests/unit/test_simulator.py` (primer test directo que tiene `simulator.py` en el proyecto).

**Hallazgo adicional, no arreglado en esta pasada (fuera del alcance pedido):**
`history_cache.py::filter_range()` filtra por `timestamp.dt.date()` sobre el timestamp crudo, que
es **UTC**, no hora NY — para un `fecha` que se interpreta como día de trading NY, el filtro en
realidad agarra un rango corrido ~5 horas (parte de la sesión NY del día anterior + parte de la
de hoy, según la época del año por el cambio de horario EST/EDT). El fix de este punto 7 mitiga
el síntoma más grave (ya no se sostiene la posición hasta la medianoche), pero no corrige de raíz
qué velas exactas componen "el día" que llega a `simular()`. No bloquea el módulo 3BP ni nada de
lo ya implementado — atado explícitamente como checkpoint obligatorio del paso 4 (backtest
walker) en "Orden de trabajo acordado", no dejado como nota suelta acá.

### 8. Backtest

- Reutilizar la metodología ya usada para calibrar los 6 criterios (Optuna, universo curado
  2023-2026) pero como corrida **separada**, no mezclada con esa calibración.
- Métricas a producir: frecuencia del patrón por ticker/día, win rate y distribución de R por
  tier de confirmación (con/sin volumen), sensibilidad de los parámetros k (multiplicador WRB),
  tolerancia de "máximos iguales", y N de invalidación.
- **Verificar antes de dimensionar el backtest:** cuánta historia de velas de 5m/15m entrega la
  API de Schwab por ticker (la retención intradía suele ser bastante más corta que la diaria que
  ya se usó para la calibración de los 6 criterios) — esto acota el período real disponible para
  testear el patrón.

---

## Fuera de alcance en esta fase (backlog explícito, no construir todavía)

- **Timeframes rápidos (1m/2m), pendiente de infraestructura.** Unificado en un solo ítem — no
  son dos pendientes separados. Bloqueante real (ver corrección al inicio del documento): Schwab
  no ofrece frecuencia de 2 minutos (solo 1/5/10/15/30), así que 2m requeriría construir soporte
  de 1m (`schwab_history.py`/`history_cache.py` no lo tienen hoy) + resampleo a 2m, tanto para el
  stream en vivo como para el historial de backtest — infraestructura nueva, no una capa liviana.
  Evaluar más adelante, después de tener 5m/15m funcionando y calibrado.
- Variantes bajistas -3BP/-4BP.
- Cola de detección en daily/weekly (versión swing del mismo patrón) — queda anotada para
  evaluar más adelante, no se define universo ni cadencia todavía.
- **Detección de 3BP en pre-market, unificada con Super Curl como trabajo futuro relacionado —
  no son dos pendientes aislados, es la misma razón de fondo.** Las series de 3BP (`velas_3bp_5m`/
  `_15m`, paso 3) arrancan vacías cada día a propósito, sin heredar contexto de pre-market — ver
  el punto ciego concreto documentado en el paso 3 de "Orden de trabajo acordado" (sin señales
  posibles en los primeros 15-45 min de sesión). Cualquier futuro soporte de pre-market para 3BP
  debería diseñarse junto con Super Curl (que por definición **es** un patrón de pre-market: gap +
  consolidación + breakout), no por separado.
- Super Curl (gap + pullback + breakout) — sumar de forma incremental después de validar 3BP.
- Reconciliar la definición de `PARTIAL_SCALE` (salida parcial en 1R fijo vs. primera resistencia
  técnica — hoy los documentos del sistema no coinciden entre sí). No bloquea esta fase porque el
  default elegido para 3BP es `FIXED_RR`, no `PARTIAL_SCALE`.
- Cualquier paso a ejecución real / producción.

---

## Parámetros iniciales propuestos (placeholders, sin calibrar)

| Parámetro | Valor de partida propuesto | Estado | Alcance |
|---|---|---|---|
| Multiplicador WRB (k) | 2 × ATR14 | A calibrar | Por timeframe |
| Tolerancia "máximos relativamente iguales" | ±20-30% del rango de barra 1 (25% usado como punto medio) | A calibrar | Por timeframe |
| N barras de expiración (invalidación) | 10 (placeholder, sin propuesta original) | A definir con backtest | Por timeframe |
| Target R (perfil FIXED_RR específico 3BP) | 3.0 (placeholder, sin definir en la charla original) | A definir con backtest | Por timeframe |
| Ventana de inicio (barras previas sin WRB) | 4 (dentro del rango "3-5" propuesto) | A calibrar | Por timeframe |
| Umbral de volumen para tier "confirmado" | ≥ 2× promedio en barra gatillo | A calibrar | Compartido |
| Target R (perfil FIXED_RR genérico) | Confirmar valor actual del sistema | Verificar | N/A — es `rr_target`, no un campo nuevo |

Nota: **12 campos por-timeframe en total** (5 parámetros × 2 timeframes: `bp34_wrb_multiplicador`,
`bp34_tolerancia_pct`, `bp34_n_invalidacion`, `bp34_target_r`, `bp34_ventana_inicio_barras`, cada
uno con sufijo `_5m`/`_15m`) + **1 compartido** (`bp34_volumen_confirmado_mult`) — campos planos en
`ScanConfig`, mismo patrón que el escalado de precio del filtro de variación diaria, sin
estructura anidada (ver corrección al inicio del documento). Detalle de por qué cada uno quedó
por-timeframe o compartido, en el punto 2 de "Orden de trabajo acordado".

---

## Orden de trabajo acordado

1. **Fix del cierre forzado EOD (sección 7) ✅ hecho** — ver detalle arriba.
2. **Módulo de detección puro ✅ hecho** — `engine/pattern_3bp.py`: `Detector3BP`, máquina de
   estados en memoria (una instancia por ticker+timeframe), sin dependencia de Schwab ni del
   stream — `procesar_barra(vela, atr14, volumen_promedio)` se llama una vez por vela ya cerrada
   y devuelve un evento solo en las transiciones (POSIBLE/ESPERANDO_ENTRADA/ENTRADA/vuelta a
   SIN_PATRON), `None` si la vela no cambió nada. 14 tests en `tests/unit/test_pattern_3bp.py`,
   incluyendo el ejemplo numérico exacto de la spec (barra 1 min=2/max=10/pm=6).

   **Interpretaciones no 100% literales de la spec — confirmadas después de revisión, con el
   detalle completo de qué decía la spec, la ambigüedad y la decisión final:**

   - **(a) Barra que no confirma grupo ni invalida, inmediatamente después de la barra 1.** La
     spec (sección 2) define "confirma grupo" (mínimo ≥ pm, máximo ≤ techo) e "invalida" (cierra
     bajo el mínimo de barra 1), pero nunca contempla el tercer caso: una barra que no hace
     ninguna de las dos cosas. **Decisión confirmada:** se descarta el patrón entero y se vuelve
     a `SIN_PATRON` — no se espera a una barra futura no inmediata. Motivo: el patrón se define
     como barras **consecutivas** (barra 1, barra 2, barra 3/4, en ese orden inmediato — así lo
     describe el curso en cada ejemplo), no "barra 1 y en algún momento posterior una que
     califique". Se descartó tratar una ruptura inmediata (sin ninguna barra de grupo) como un
     "gatillo de 2 barras" válido, porque la spec es explícita en que el mínimo son 3 barras.
   - **(b) Qué barras cuentan para el N de invalidación en Estado 2.** La spec (sección 3) dice
     "pasan más de N barras sin ruptura desde que se alcanzó Estado 2", sin aclarar si N cuenta
     *todas* las barras transcurridas o solo las que *no* confirman grupo. **Decisión
     confirmada: interpretación (i)** — el contador suma en cada barra dentro de
     `ESPERANDO_ENTRADA`, confirme grupo o no. Se descartó la interpretación (ii) (contar solo
     barras "fallidas") porque permitiría que el patrón se extendiera sin límite mientras cada
     barra nueva siguiera confirmando tolerancia. **Verificado explícitamente que ese escenario
     era real y no estaba evitado por otro lado:** el grupo no tenía ningún tope duro de tamaño
     en la primera versión del código — cualquier barra que confirmaba la condición de
     posición/techo se agregaba sin chequear cuántas ya había, así que sin la interpretación (i)
     el grupo sí podría haber crecido indefinidamente.

   **Hallazgo posterior, corregido antes de cerrar este paso:** la nota de arriba decía, sin
   corregir, que "un grupo de 3+ barras igual se reporta como `tipo='4BP'`" — eso contradice
   directamente el motivo por el que en (a) se descartó dejar que el patrón se extendiera más
   allá de barras consecutivas acotadas: "3 y 4 Bar Play" es una definición **cerrada**, no
   "N Bar Play". Dejarlo así habría sido inconsistente con la propia decisión de (a) en el mismo
   documento. **Fix aplicado:** el grupo ahora tiene tope duro de 2 barras (`_GRUPO_MAX_BARRAS`
   en `pattern_3bp.py`, barra 2 + barra 3 = máximo 4BP). Si aparece una barra candidata a una
   3ra barra de grupo (confirma la condición de posición/techo) pero el grupo ya está en el tope,
   el patrón se descarta directo (`SIN_PATRON`) en vez de seguir extendiéndolo — mismo criterio
   que (a): sin estructura válida, no hay señal. Con el tope, `tipo = "3BP" if len(grupo)==1
   else "4BP"` deja de tener ambigüedad (el "else" ahora solo puede significar `len(grupo)==2`).
   Test agregado: `test_descarta_el_patron_si_una_tercera_barra_candidata_a_grupo_excede_el_tope`.

   **Campos de `ScanConfig` — 12 en total (5 parámetros × 2 timeframes, después de la corrección
   de abajo) + 1 compartido:**
   - Por timeframe (`_5m`/`_15m`): `bp34_wrb_multiplicador`, `bp34_tolerancia_pct`,
     `bp34_n_invalidacion`, `bp34_target_r`, y **`bp34_ventana_inicio_barras`** (corregido — ver
     abajo, antes estaba compartido por error de categorización).
   - Compartido: `bp34_volumen_confirmado_mult` — esto **sí** está respaldado textualmente por la
     spec, no es una relajación: la sección 1 enumera taxativamente los 4 parámetros "por
     timeframe" (WRB, tolerancia, N de invalidación, target R) y el umbral de volumen no está en
     esa lista; la sección 9 también lo trata como una sola fila, no una por timeframe.
   - Ninguno de los 12+1 campos tocado por el optimizador (verificado, `search_space.py` no los
     referencia).

   **Corrección: `bp34_ventana_inicio_barras` pasa de compartido a por-timeframe.** A diferencia
   de `bp34_volumen_confirmado_mult`, este parámetro (la ventana de "3-5 barras" para chequear
   que la barra 1 "inicia" un movimiento, sección 2) **no tenía respaldo textual** para quedar
   compartido — la spec original nunca lo categorizó ni en la lista de la sección 1 ni en la
   tabla de la sección 9 (quedó sin asignar en la versión previa del documento). Se corrigió a
   por-timeframe (`bp34_ventana_inicio_barras_5m` / `_15m`) porque 4 barras representan
   contextos de mercado muy distintos según el timeframe (~15-25 min en 5m contra ~45-75 min en
   15m) — no tiene sentido calificar "inicio de movimiento" con la misma vara en los dos.
3. **Wireo en vivo ✅ hecho** — `market_data_cache.py`: `TickerCache` suma `velas_3bp_5m` /
   `velas_3bp_15m` (bucketeo de 1m→5m y 1m→15m en paralelo, vía `_actualizar_bucket()`
   compartida — refactor de la lógica de bucketeo que antes solo existía para 5m) +
   `detector_3bp_5m` / `detector_3bp_15m` (instanciados en `seed()` con los parámetros de
   `ScanConfig` del timeframe correspondiente) + `ultimo_evento_3bp_5m` / `_15m`.
   `actualizar_vela_1m()` alimenta ambos detectores en cada tick, sin afectar el `evento`
   booleano que dispara la reevaluación del clasificador de 6 criterios (independiente, como
   pide la spec). ATR14 y volumen promedio de referencia se calculan sobre la propia serie de
   3BP (mismo timeframe), no sobre el ATR%/volumen diario que ya usa el clasificador.

   **Decisión de diseño tomada durante la implementación, confirmada:** `velas_3bp_5m`/`_15m`
   son series **propias**, deliberadamente sin sembrar con el contexto histórico de pre-market
   (a diferencia de `velas_hoy`, que sí se siembra desde `df_5m` para que la EMA del clasificador
   tenga continuidad). Motivo: `velas_hoy`/`df_15m` ya traen ~1-5 días de historial al sembrarse,
   y dejar que el patrón 3BP arrancara con esa ventana le daría contexto de días previos a la
   sesión de hoy — no encaja con el encuadre "en tiempo real... para el universo de candidatos
   del día" de la spec. Consistente con haber dejado el análisis de patrones de pre-market
   (Super Curl / gap rating) explícitamente fuera de alcance — ver referencia cruzada en "Fuera
   de alcance" más abajo.

   **Punto ciego concreto que genera esta decisión — documentado ahora, no como sorpresa cuando
   se evalúen los resultados del modo shadow más adelante:** recién a partir de la 3ra vela
   cerrada del día (2 velas de contexto + la evaluada) el detector empieza a recibir barras —
   antes de eso, `_atr14_de_velas()` no tiene suficiente contexto y se salta la evaluación. En
   números: **sin señales posibles en los primeros 15 minutos de sesión en 5m** (3 velas × 5 min)
   **ni en los primeros 45 minutos en 15m** (3 velas × 15 min) — justo la ventana que el curso
   señala como el mejor caso de uso de 3BP ("momentum de la mañana temprano", ver `Resumen Live
   Traders...md`, Parte 10). Si se prefiere sembrar con historial como el resto del sistema (y
   así cerrar este punto ciego), es un cambio acotado a `seed()`.

   4 tests nuevos en `tests/unit/test_market_data_cache_3bp.py` (series separadas del historial,
   detectores instanciados con la config correcta, bucketeo 5m/15m en paralelo sin interferirse,
   y detección real de una barra 1 WRB a través del wireo completo).
4. **Backtest walker nuevo ✅ hecho (2026-08-04)** — basado en el patrón de `backtest/simulator.py` (que ya camina vela
   por vela), no en `backtest/runner.py` (que evalúa "un día = un contexto" con lookups `asof`,
   forma incompatible con una máquina de estados intradía).

   **Checkpoint obligatorio antes de escribir el walker ✅ resuelto.**

   **1. Confirmado con datos reales (no solo inspección de código):** pedir `fecha=2026-01-15`
   contra `backtest_data/AAL/5m/2026/01.parquet` devolvía velas desde **2026-01-14 19:00 NY hasta
   2026-01-15 18:50 NY** — mezclando dos días de trading. Peor todavía: la vela de **entrada** de
   la simulación (`velas_dia["open"][0]`) resultaba ser la de la tarde/noche del día anterior
   (2026-01-14 19:00 NY, open=15.08), no la apertura real del día pedido (2026-01-15 9:30 NY,
   open=15.24) — 70 de 168 velas (42%) del "día" simulado eran de la sesión equivocada. Esto
   contaminaba entrada, stop, target y cierre EOD de cada trade simulado, no solo el cierre (que
   ya se había mitigado en el punto 7).

   **2. Mapeo de impacto, antes de tocar nada:**

   | Dónde | Timeframe | ¿Afectado en la práctica? |
   |---|---|---|
   | `runner.py:268` → `velas_dia` → `simular()` | 5m | **Sí, gravemente** |
   | `history_cache.get_history()` internamente | cualquiera | Solo en rangos anchos (años) — corrimiento de ~5h en los bordes, despreciable |
   | `runner.py:207` → `_recortar_pandas(pdf_d_full, ...)` | diario | No, por casualidad — las velas diarias de Schwab están a las 05:00 UTC, que cae en la misma fecha calendario NY tanto en EST como en EDT. Coincidencia frágil, no una garantía de diseño. |

   El motor de clasificación (score, DAY/SWING/DESCARTAR) usa velas diarias — no afectado por
   este hallazgo puntual. El **resultado de cada trade simulado** en
   `docs/resumen_optimizador_2026-07.md` (win rate 71.4%, profit factor 9.06, expectancy 0.476R,
   max drawdown 0.41R, 7 trades) sí viene de `simular()` alimentado con `velas_dia` — **esos
   números muy probablemente cambian** al corregir esto. **`docs/resumen_optimizador_2026-07.md`
   queda pendiente de una nota de advertencia explícita** marcándolos como no confiables hasta
   una re-corrida — no se agregó todavía porque es una decisión pendiente de discusión aparte
   (ver hallazgo #2 más abajo, que también afecta esos mismos números y conviene resolver antes
   de decidir si re-correr una vez o dos).

   **3. Fix aplicado:** `history_cache.py::filter_range()` ahora convierte a hora NY antes de
   extraer la fecha (los timestamps de Schwab son naive-pero-UTC, nunca hora NY — mismo patrón ya
   usado en `simulator.py::_truncar_a_cierre_forzado`). 8 tests nuevos en
   `tests/unit/test_history_cache_filter_range.py`, incluyendo los dos casos límite de cambio de
   horario (transición a EDT en marzo 2026 y a EST en noviembre 2026) y un caso defensivo para
   timestamps que ya llegan con timezone. `_recortar_pandas()` (pandas, usado solo para contexto
   diario) **no se tocó** — no tiene el bug en la práctica hoy (ver mapeo arriba), y tocarlo habría
   exigido un índice tz-aware en todo el hot path de `runner.py` (`_valor_asof` incluido) por una
   ganancia real nula en el caso de uso actual (solo diario). Documentado como riesgo latente si
   alguna vez se reusa para intradía — el walker del paso 4 no debe reusar `_recortar_pandas` para
   slicing intradía sin revisar esto primero.

   **4. Hallazgo #2 — ✅ corregido (2026-08-03).**
   Al corregir los fixtures de test para usar el horario real de las velas diarias de Schwab
   (05:00 UTC, no medianoche — necesario para que `filter_range()` fijo no divergiera de
   `_recortar_pandas` en los tests de equivalencia), se había destapado un bug real y separado en
   `runner.py::_valor_asof()`: construía la consulta `asof` como `pd.Timestamp(dia)` (medianoche),
   pero la vela diaria real de `dia` está a las 05:00 UTC (después de medianoche) — así que
   `.asof(medianoche)` la excluía y devolvía la vela del día **anterior**. Confirmado con datos
   reales de AAL: pedir "el valor de ayer" (`fin_contexto`=2021-05-19) devolvía el close de
   **2021-05-18** (23.56), no el de 2021-05-19 (22.97). Afectaba `cruce_ema_921_d/_5m/_15m/_4h`,
   `sobre_sma200`/pivotes y `atr_pct` — es decir, la **clasificación** (score, DAY/SWING), no solo
   la simulación de posición. Confirmado que es exclusivo del camino de backtest/optimizador
   vectorizado — el pipeline en vivo (`pipeline.py` → `engine/signals.py::detect_setup_timeframe`)
   no pasa por `runner.py` ni por `_valor_asof`, calcula directo sobre datos frescos. Las
   clasificaciones DAY/SWING de hoy en el scanner en vivo nunca estuvieron afectadas.

   **Fix:** `_valor_asof()` ahora calcula el límite de consulta como el cierre del día de trading
   NY `dia` — el instante justo antes de la medianoche NY de `dia + 1`, convertido a su
   equivalente UTC naive (mismo patrón de conversión a `America/New_York` ya usado en
   `filter_range()`; nunca se usa la hora local de Buenos Aires para esto — ver discusión de
   zonas horarias más abajo). Esto cubre tanto la convención diaria real de Schwab (05:00 UTC)
   como cualquier hora dentro del día para las series intradía precalculadas, sin depender de a
   qué hora exacta cae el timestamp. Los 7 tests que estaban `xfail` en
   `test_runner_equivalencia_pandas.py` y `test_runner_equivalencia_end_to_end.py` vuelven a
   correr sin el marcador y pasan (verificado, más el resto de la suite: 195 tests, 0 fallos).

   **Pendiente de decisión, no forma parte del módulo 3BP:** `docs/resumen_optimizador_2026-07.md`
   (71.4% win rate, profit factor 9.06, 7 trades) se calculó con ambos bugs presentes — sigue sin
   la nota de advertencia y sin decidir si conviene una sola re-corrida del optimizador combinando
   ambos fixes.

   **Nota sobre zonas horarias para más adelante (Sprint 5, ejecución de órdenes):** el patrón ya
   establecido en todo el sistema es UTC para persistir timestamps y `America/New_York` para
   cualquier decisión de límites de sesión/día (mismo criterio que `_en_horario_habil()` en
   `schwab_client.py`). Buenos Aires no participa de ninguna lógica de trading — a lo sumo,
   cuando haya fills de órdenes reales, se podría convertir la hora de ejecución a Buenos Aires
   solo para mostrarla en la UI, nunca para decidir nada (límites de día, cierre forzado EOD, etc.).

   **El walker en sí — ✅ implementado (2026-08-04).**

   `backtest/walker_3bp.py::caminar_3bp(ticker, timeframe, fecha_inicio, fecha_fin, config)` —
   caminador vela por vela, reusa el mismo `Detector3BP` que corre en vivo. Replica exactamente el
   reseteo diario que ya hace `market_data_cache.py::seed()`: un `Detector3BP` fresco y un
   contexto vacío por cada día de trading (mismo "punto ciego" de los primeros ~15-45 minutos de
   sesión, documentado en el paso 3, también presente acá por construcción). ATR14 y volumen
   promedio de referencia se calculan con las mismas funciones privadas que ya usa el stream
   (`_atr14_de_velas`, `_volumen_promedio_de_velas`, `_a_vela_pattern`, `_crear_detector_3bp`,
   importadas de `market_data_cache.py` en vez de reimplementarlas). Un mismo día puede producir
   varias entradas independientes (el detector vuelve a `SIN_PATRON` apenas emite `ENTRADA`).

   Cada entrada (Estado 3) se sigue con el precio real post-señal **dentro del mismo día**
   (3BP es una señal de timing intradía — la spec no define sostenimiento multi-día para este
   módulo, a diferencia del SWING del clasificador de 6 criterios) hasta tocar target, tocar stop,
   o el cierre forzado a las 15:55 NY (`simulator.py::_truncar_a_cierre_forzado`, reusada — ahora
   acepta un `fecha_limite` opcional, ver el fix de SWING más abajo en el changelog del backlog).
   Si una barra toca stop y target a la vez, gana el stop (mismo criterio pesimista que
   `simulator.py::_fixed_rr`) — con solo OHLC no hay forma de saber el orden real intra-barra. La
   barra gatillo misma se revisa también (el breakout que dispara la entrada puede seguir
   moviéndose, o revertir, en esa misma barra).

   `backtest/metrics_3bp.py` agrega resultados en un `Bp34BacktestRun` — corrida separada del
   optimizador de 6 criterios (nunca mezclados), un timeframe por corrida. Reusa los helpers puros
   de `backtest/metrics.py` (`_win_rate`, `_rr_promedio`, `_profit_factor`) por duck-typing sobre
   `.resultado_r` — no hace falta reimplementarlos. Solo persiste el agregado (mismo criterio que
   `run_backtest()` del clasificador, que tampoco persiste cada `ScanResult` de un backtest).

   **Modelo y persistencia — vivo y backtest comparten la misma tabla.** `Bp34Evento` (nuevo en
   `models.py`) sigue el mismo patrón que `ScanResult`/`FuenteDatos` (`LIVE`/`HISTORICO`). Tabla
   `bp34_eventos` en Turso, separada de `scan_results`/`backtest_runs` — nunca mezclada con el
   clasificador de 6 criterios. Esto cierra un gap real encontrado al arrancar este paso: el wireo
   en vivo (paso 3) generaba eventos pero no los persistía en ningún lado ni los mostraba — la
   sección 6 de esta spec ("modo shadow") hablaba de "registrar la operación" pero eso no pasaba
   en la práctica. Fix: `MarketDataCache` gana una cola (`_eventos_3bp_pendientes` +
   `drenar_eventos_3bp()`) que se llena cuando `_procesar_3bp` recibe un evento en Estado `ENTRADA`
   — drenada por `schwab_stream.py::_despachar_eventos_3bp()` (mismo patrón `asyncio.create_task`
   que ya usa `_despachar_si_evento` para no bloquear `handle_message()`), llamada después de cada
   `actualizar_vela_1m()` (real y mock). `main.py::_on_evento_3bp` persiste con `fuente=LIVE`.

   **Limitación deliberada del MVP en vivo, documentada a propósito:** solo se persiste la entrada
   (`resultado=ABIERTO`) — el seguimiento del resultado real (tocó target/stop) todavía **no**
   está implementado para el modo vivo, a diferencia del backtest (que sí sigue el precio histórico
   completo post-señal). Cerrarlo requeriría trackear posiciones abiertas contra el stream en
   tiempo real, fuera de alcance de este paso — anotado como pendiente, no una sorpresa a
   descubrir después.

   Página `/patrones-3bp` (`api/patrones_3bp.py` + `templates/patrones_3bp.html`) — separada del
   dashboard y de `/backtest` (spec, sección 5: "no se mezcla con el score"), mismo patrón HTMX que
   el resto del sistema. Muestra eventos recientes (vivo + backtest) y corridas de backtest
   pasadas; formulario para lanzar un backtest nuevo (tickers, timeframe, rango de fechas).

   27 tests nuevos (`test_walker_3bp.py`, `test_metrics_3bp.py`, + extensiones a
   `test_schwab_stream.py` y `test_market_data_cache_3bp.py`) — incluye el ejemplo numérico exacto
   de la spec llevado de punta a punta a través del walker (no solo del detector puro, que ya
   estaba cubierto). Suite completa: 220 tests, 0 fallos.

   **Pendiente, fuera de esta pasada:** calibrar los 12+1 campos `bp34_*` con Optuna (siguen en los
   placeholders de la spec — k=2, N=10, target=3.0R, tolerancia=25%, ver tabla más abajo); validar
   la profundidad real de historial de 5m/15m contra Schwab para este módulo específicamente (ya
   se sabe en general que arranca ~nov-2025, ver CLAUDE.md, pero no se corrió un backtest real
   todavía para confirmar cuántas señales produce en la práctica); seguimiento de resultado en
   vivo (ver limitación de arriba).
