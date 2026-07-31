# Spec (propuesta, sin confirmar): estructura de pivotes para el criterio 5

Reemplaza el bit binario de `criterio_sma200` por estructura de pivotes (HPH/HPL vs LPH/LPL),
+ EMA200 como referencia adicional. Ver `docs/backlog_mejoras_clasificador.md`, Prioridad 1.

**Estado: propuesta a confirmar, no implementado.** Mismo nivel de precisión que
`spec_modulo_3bp_4bp.md` — cada número tiene un ejemplo concreto al lado.

---

## 1. Datos de entrada

Reusa exactamente lo que ya se descarga — sin datos nuevos:

- Serie: `df_d` (velas diarias), mismas que hoy calculan `sobre_sma200` en `signals.py`.
- Ventana disponible: `config.velas_diarias` (default 252, ~1 año).
- Escala de "ruido vs. movimiento real": `ATR14` diario, ya calculado por el sistema
  (`calc_atr_pct` / mismo insumo que usa la spec de 3BP para su rango de referencia).

---

## 2. Definición de pivote (fractal simétrico)

**Ventana `L` (barras a cada lado):** punto de partida propuesto `L = 3` (fractal de 7 barras:
3 antes + la barra + 3 después). Más chico (`L=2`) da más pivotes pero más ruido; más grande
(`L=5`) da pivotes más significativos pero menos cantidad y más lag. **A confirmar/calibrar.**

**Condición exacta — pivote alto en la barra `i`:**
```
high[i] > high[i-L], high[i-L+1], ..., high[i-1]   (estrictamente mayor que las L barras previas)
  Y
high[i] > high[i+1], ..., high[i+L]                 (estrictamente mayor que las L barras siguientes)
```
**Pivote bajo en la barra `i`:** espejo, con `low[i]` estrictamente menor que las `2L` barras vecinas.

**Consecuencia de diseño (a tener presente, no a decidir):** un pivote en la barra `i` recién
puede confirmarse cuando existen las `L` barras posteriores — con `L=3` en velas diarias, un
pivote de "hoy" nunca está disponible; el más reciente utilizable tiene como mínimo 3 días
hábiles de antigüedad. Mismo tipo de lag estructural que ya documenta la spec de 3BP para su
invalidación por N barras — no es un bug, es inherente a cualquier definición de pivote por
fractal.

**Ejemplo numérico (detección de UN pivote alto, `L=3`):**

Serie de máximos diarios (índice 0 = más antiguo):
```
idx:   0    1    2    3    4    5    6    7    8    9    10   11
high: 10.0 10.5 11.2 10.8 10.3  9.9 10.4 11.0 11.8 11.3 10.9 10.5
```
Evaluando `idx=8` (high=11.8):
- 3 barras previas (idx 5,6,7): 9.9, 10.4, 11.0 — todas < 11.8 ✓
- 3 barras siguientes (idx 9,10,11): 11.3, 10.9, 10.5 — todas < 11.8 ✓
- → **Pivote alto confirmado en idx=8, valor 11.8** (recién sabible una vez existe idx=11).

Evaluando `idx=3` (high=10.8): la barra previa `idx=2` vale 11.2 > 10.8 → **no es pivote** (falla
la condición apenas en la primera barra vecina, no hace falta seguir comparando).

Los pivotes bajos se detectan igual, sobre la columna `low`, de forma completamente
independiente de los pivotes altos (no se fuerza alternancia alto/bajo/alto como en un ZigZag —
se arman dos listas separadas: `pivotes_altos` y `pivotes_bajos`).

---

## 3. Tolerancia para comparar pivotes entre sí

Un pivote nuevo cuenta como genuinamente "mayor" o "menor" que el anterior solo si la diferencia
supera un margen expresado en ATR (para no contar como tendencia una diferencia de centavos que
es ruido). Con `tolerancia_atr` como parámetro (punto de partida propuesto: **0.5**, a calibrar,
mismo espíritu que el ±20-30% de 3BP):

```
diferencia = pivote_actual − pivote_anterior
margen = tolerancia_atr × ATR14_diario

diferencia >  margen   →  "Mayor" (Higher)
diferencia < -margen   →  "Menor" (Lower)
|diferencia| ≤ margen  →  "Igual" (Equal — rompe la racha, no cuenta ni como Higher ni Lower)
```

**Ejemplo numérico:** `ATR14 = $2.00`, `tolerancia_atr = 0.5` → margen = `$1.00`.
- Pivote alto anterior `$50.00`, pivote alto actual `$50.80` → diferencia `$0.80` ≤ `$1.00` →
  **"Igual"**, no cuenta como Higher pese a que nominalmente subió.
- Pivote alto actual `$51.20` en cambio → diferencia `$1.20` > `$1.00` → **"Higher"** confirmado.

---

## 4. Cuántos pivotes confirman la estructura

Mínimo propuesto: **2 pivotes consecutivos de cada tipo** (comparar el último confirmado contra
el anteúltimo) — mismo piso que usa el curso para sus patrones ("2 o más máximos decrecientes").
Parametrizado como `pivotes_minimos_consecutivos` (default 2) por si se prefiere exigir una racha
más larga (3) para más confianza. **A confirmar.**

```
Estructura ALCISTA  ⟺  último pivote alto es "Higher" Y último pivote bajo es "Higher"  (HPH + HPL)
Estructura BAJISTA  ⟺  último pivote alto es "Lower"  Y último pivote bajo es "Lower"   (LPH + LPL)
Cualquier otra combinación (mixta, "Igual", o menos de 2 pivotes de algún tipo) → INDETERMINADA
```

---

## 5. Qué pasa en el caso INDETERMINADA — decisión a confirmar

Con datos insuficientes (ticker con poco historial, ej. IPO reciente) o estructura mixta, hay dos
caminos posibles y **no está decidido cuál tomar**:

- **(a) Fallback al bit binario actual** (`sobre_sma200`) — el criterio nunca queda "más pobre"
  que hoy, solo mejora cuando hay pivotes claros que confirmar. Es lo que yo recomendaría: menos
  riesgo de que suban los `DESCARTAR` por `INSUFICIENTE_DATA` en tickers con historial corto.
- **(b) Devolver `None`** (criterio incompleto, no penaliza per Regla 2, pero no aporta score) —
  más "puro" conceptualmente (no mezcla dos fuentes de señal distintas) pero puede bajar la
  cantidad de criterios calculables en más tickers de los que hoy caen en ese caso con el bit
  binario simple.

**Recomiendo (a), pero es la decisión más importante de esta spec — confirmarla antes de codear.**

---

## 6. EMA200 — desviación del curso a confirmar

El curso pide EMA200 en **60'/diario**. El sistema hoy **no descarga velas de 60'** (solo
5m/15m/4h/d) — agregar un timeframe nuevo implica tocar `pipeline.py`, `schwab_history.py` y
`ScanConfig` (nueva cantidad de velas a pedir), bastante más alcance que "prácticamente gratis".

**Propuesta:** calcular la EMA200 sobre **diario** (`df_d`, que ya se descarga), no sobre 60'.
Se agrega como campo puramente informativo (ej. `ema200_diaria` en `DatosTickerCompletos` /
`ScanResult`, visible en el detalle del ticker) — **no entra al score**, no toca `criteria.py`.
**A confirmar si esta desviación (diario en vez de 60') es aceptable, o si amerita sumar el
timeframe de 60' en otro momento.**

---

## 7. Dónde vive esto en el código (arquitectura, no implementación)

Mismo patrón que ya usa `sobre_sma200` hoy — cálculo pesado una sola vez en `signals.py` a
partir de `df_d`, el criterio en `criteria.py` solo mapea el resultado ya calculado a
`(score_day, score_swing)`:

- `indicators/trend.py` o un módulo nuevo `engine/pivots.py`: función pura
  `detect_estructura_pivotes(df_d, config) -> Literal["ALCISTA","BAJISTA","INDETERMINADA"]`
  (testeable en aislado con series construidas a mano, sin red ni Schwab).
- `signals.py::detect_setup_timeframe`: agrega `"estructura_pivotes"` al dict que ya devuelve,
  junto al `sobre_sma200` existente (que se mantiene, se usa como fallback — ver punto 5).
- `DatosTickerCompletos`: nuevo campo `estructura_pivotes: Optional[str]`.
- `criteria.py::criterio_sma200`: cambia de firma — de `(sobre_sma200: bool)` a
  `(estructura_pivotes, sobre_sma200)`, mapea ALCISTA→`(1.0,0.0)`, BAJISTA→`(0.0,1.0)`,
  INDETERMINADA→fallback al bit binario (punto 5-a). Mismo nombre de función y mismo
  `peso_sma200` en `ScanConfig` — no se renombra el criterio ni se toca el espacio de pesos.
- 3 campos nuevos de config (`pivote_ventana_l`, `pivote_tolerancia_atr`,
  `pivote_minimos_consecutivos`) — no son `peso_*`, no entran al optimizador salvo que se decida
  explícitamente agregarlos a `search_space.py` más adelante (no en esta pasada).

---

## Resumen de lo que falta confirmar antes de codear

1. `L = 3` (ventana del fractal) — ¿de acuerdo, o preferís arrancar con otro valor?
2. `tolerancia_atr = 0.5` — ¿de acuerdo?
3. `pivotes_minimos_consecutivos = 2` — ¿alcanza, o preferís exigir 3 de entrada?
4. Caso INDETERMINADA → **(a) fallback a `sobre_sma200`** (recomendado) vs. (b) `None`.
5. EMA200 sobre **diario** (no 60') — ¿aceptable por ahora?
