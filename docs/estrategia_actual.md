# Cómo opera el sistema hoy — para charlar estrategia

Este documento es un resumen de la lógica de trading actual, sin detalle de implementación
(código, archivos, stack). Pensado para llevar a una charla de "qué otra estrategia probar",
no para un agente de código — para eso está `CLAUDE.md`.

---

## Qué hace el sistema, en una frase

Todos los días, antes de la apertura, toma la lista de candidatos que ya filtró el trader en
ThinkOrSwim (Stock Hacker), le agrega datos técnicos e históricos de Schwab, y clasifica cada
ticker como oportunidad de **DAY trade**, **SWING trade**, o lo descarta — con un score, no una
decisión binaria arbitraria. Durante la sesión, sigue reevaluando cada ticker en tiempo real con
datos del stream (WebSocket) cuando pasa algo relevante (cruce de EMA, cruce de VWAP, cambio de
volumen relativo, nuevo máximo/mínimo del día).

## Qué se espera del sistema

- **No decide por el trader.** Prioriza y clasifica candidatos que el trader ya preseleccionó a
  mano en ToS — el filtro humano (mirar el gráfico, el contexto de mercado) sigue siendo el primer
  filtro, el sistema es el segundo.
- **Preservación de capital por encima de frecuencia de operación.** Es una regla explícita del
  proyecto: prefiere quedarse afuera antes que forzar una entrada dudosa.
- **Reproducibilidad total.** Cada resultado guarda una foto completa de la configuración usada
  ese día — se puede reconstruir exactamente por qué un ticker clasificó como DAY o SWING meses
  después.
- **El mismo motor evalúa en vivo y en backtest.** No hay lógica separada "para probar" y "para
  operar" — lo que se calibra contra histórico es literalmente lo mismo que corre en producción.

## La lógica de clasificación — los 6 criterios

Cada ticker se evalúa con 6 criterios independientes, cada uno da un puntaje hacia DAY y otro hacia
SWING (no son excluyentes — un ticker puede puntuar para ambos). Se suman con pesos (hoy todos
los pesos están en 1.0 — pesos parejos, ver más abajo por qué):

1. **Setup de timeframe** — si la tendencia de EMA rápida/lenta está alineada a favor en 5m/15m/4h/diario.
2. **Catalizador** — si hay un evento relevante en las próximas 24h (earnings, evento macro, 8-K,
   upgrade/downgrade), vía un semáforo GREEN/YELLOW/RED de otro sistema (Trading Calendar). Un
   RED no descarta la operación — condiciona a estrategias con riesgo definido.
3. **Volumen relativo (RelVol)** — volumen de hoy vs. promedio. Muy alto → day; moderado → swing.
4. **ATR% (volatilidad)** — rango diario como % del precio. Muy alto → day; moderado → swing.
5. **Posición vs. SMA 200** — tendencia de fondo.
6. **HV Rank (proxy de volatilidad implícita)** — volatilidad histórica rankeada contra el último
   año. Schwab no expone el rango real de IV implícita, así que esto es una aproximación con
   volatilidad histórica de precio, no de opciones.

**Antes de estos 6 criterios**, hay un filtro de entrada (precio, volumen promedio, ATR% mínimo,
RelVol mínimo, variación diaria mínima, spread bid/ask) que descarta directo un ticker no operable,
sin gastar los 6 criterios en él — misma idea que los filtros que el trader ya configura en ToS,
pero como red de seguridad del lado del sistema.

**Clasificación:** el ticker gana DAY o SWING según cuál score (ponderado) supera un umbral
mínimo y es estrictamente mayor al otro. Si empatan arriba del umbral, gana DAY por default —
la idea es que con capital limitado, una operación más corta (day) inmoviliza menos tiempo que
una posición swing. Si ninguno de los dos llega al umbral, se descarta.

**Criterios que no se pueden calcular no penalizan** — si falta un dato (ej. Schwab no tiene
historial, o el Calendar no respondió), ese criterio simplemente no participa del cálculo, ni
suma ni resta. Pero si se pudieron calcular muy pocos criterios en total, el ticker se descarta
igual — mejor incertidumbre reconocida que confianza falsa con datos incompletos.

## Gestión de la posición, una vez clasificado

Tres modos de salida configurables (hoy el default es el primero):
- **FIXED_RR** — target fijo a un múltiplo de R (riesgo) configurable, stop basado en ATR.
- **TRAILING_EOD** — stop dinámico que se ajusta vela a vela, cierre forzado a las 15:55 ET.
- **PARTIAL_SCALE** — 50% de la posición sale en la primera resistencia técnica, el resto sigue
  con trailing.

Todo se mide en múltiplos de R (riesgo unitario), no en dólares — el sistema nunca trackeó
tamaño de posición ni capital de cuenta real.

## Qué encontró la calibración hasta ahora (ver detalle en `resumen_optimizador_2026-07.md`)

El optimizador (Optuna, 50 trials sobre 287 tickers curados, 2023–2026) encontró que la mejor
configuración es **muy selectiva**: umbral de decisión alto (~4.76 sobre un máximo posible de 6),
lo que da pocos trades (7 en el backtest) pero muy eficientes — 71% de aciertos, profit factor 9,
expectancy +0.48 R por operación. Bajar el umbral dispara la cantidad de operaciones pero el
resultado se vuelve claramente negativo.

**Ojo con este hallazgo:** todavía no está validado contra CSVs reales de ToS (universo curado ≠
exposición real del día a día), y la muestra de 7 trades es chica. Se está tratando como hipótesis
direccional, no como calibración final — ver recomendaciones en `resumen_optimizador_2026-07.md`.

## Lo que el sistema NO hace (todavía / por decisión explícita)

- No ejecuta órdenes — es puramente de análisis y clasificación (fase de ejecución real es
  trabajo futuro, sin fecha).
- No optimiza los pesos de los 6 criterios — se mantienen todos en 1.0 hasta acumular 60+ días de
  operación real registrada, para evitar overfitting con pocos datos.
- No opera fuera de lo que ya filtró el Stock Hacker de ToS — no descubre candidatos por su cuenta.
- No promedia posiciones perdedoras.
