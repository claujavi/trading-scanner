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
qué velas exactas componen "el día" que llega a `simular()`. Queda anotado para evaluar aparte —
no bloquea el módulo 3BP ni nada de lo ya implementado.

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
- Super Curl (gap + pullback + breakout) — sumar de forma incremental después de validar 3BP.
- Reconciliar la definición de `PARTIAL_SCALE` (salida parcial en 1R fijo vs. primera resistencia
  técnica — hoy los documentos del sistema no coinciden entre sí). No bloquea esta fase porque el
  default elegido para 3BP es `FIXED_RR`, no `PARTIAL_SCALE`.
- Cualquier paso a ejecución real / producción.

---

## Parámetros iniciales propuestos (placeholders, sin calibrar)

| Parámetro | Valor de partida propuesto | Estado |
|---|---|---|
| Multiplicador WRB (k) | 2 × ATR14 | A calibrar |
| Tolerancia "máximos relativamente iguales" | ±20-30% del rango de barra 1 | A calibrar |
| N barras de expiración (invalidación) | Sin propuesta | A definir con backtest |
| Umbral de volumen para tier "confirmado" | ≥ 2× promedio en barra gatillo | A calibrar |
| Target R (perfil FIXED_RR genérico) | Confirmar valor actual del sistema | Verificar |
| Target R (perfil FIXED_RR específico 3BP) | Sin definir — debería ser mayor que el genérico | A definir con backtest |

Nota: los parámetros de arriba son por timeframe — 5m y 15m van a necesitar valores propios, no
un único valor compartido (ver punto 1, "cada timeframe corre como detector independiente"). Son
**8 campos en total** (4 parámetros × 2 timeframes) como campos planos en `ScanConfig` (ej.
`bp_3_4_wrb_multiplicador_5m`, `bp_3_4_wrb_multiplicador_15m`, etc.) — mismo patrón que el
escalado de precio del filtro de variación diaria, sin estructura anidada (ver corrección al
inicio del documento).

---

## Orden de trabajo acordado

1. **Fix del cierre forzado EOD (sección 7) ✅ hecho** — ver detalle arriba.
2. **Módulo de detección puro** — función(es) testeables en aislado (máquina de estados sobre una
   serie de velas), sin dependencia de Schwab ni del stream. La definición mecánica (sección 2) ya
   está al nivel de precisión necesario para codear esto directo, sin más ida y vuelta de spec.
3. **Wireo en vivo** — expandir `market_data_cache.py` para bucketear **dos** series en paralelo
   (5m y 15m) en vez de solo 5m como hoy, y correr el detector sobre cada una.
4. **Backtest walker nuevo** — basado en el patrón de `backtest/simulator.py` (que ya camina vela
   por vela), no en `backtest/runner.py` (que evalúa "un día = un contexto" con lookups `asof`,
   forma incompatible con una máquina de estados intradía).
