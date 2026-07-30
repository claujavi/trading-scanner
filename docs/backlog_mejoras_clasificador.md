# Backlog: mejoras al clasificador de 6 criterios

Ideas que surgieron comparando `estrategia_actual.md` contra el resumen del curso Live Traders.
Ninguna está decidida ni priorizada para implementación — quedan anotadas para no perderlas,
independientes del trabajo del módulo 3BP/4BP (no lo bloquean, se retoman más adelante, en línea
con el criterio de "ir agregando de a poco").

---

## 1. Criterio "catalizador" — de semáforo a gap rating

Hoy el criterio 2 (catalizador) es un semáforo GREEN/YELLOW/RED genérico basado en si hay un
evento relevante en las próximas 24h. El curso propone un sistema más fino: rating de gaps en
Nivel 1/2/3 (con matices +/-), evaluado con 6 preguntas concretas (hacia dónde gapea, desde
dónde, valor de shock, si supera soporte/resistencia de forma justa o excesiva, si va hacia un
vacío o una resistencia, y si muestra fuerza/debilidad relativa).

También aporta un matiz que el filtro actual no tiene: el % de gap por sí solo no define
"excesivo" — depende del precio de la acción (una de $6 gapeando $1 no es lo mismo que una de $60
gapeando $10). El filtro actual de "variación diaria > ±2%" no distingue por precio.

**Status:** evaluar.

---

## 2. Criterio RelVol — tipificar el volumen, no solo un umbral

Hoy RelVol usa un único umbral genérico. El curso distingue tres tipos de volumen: Igniting
(≥2x el promedio, inicia un movimiento), Ending (≥2x, termina un movimiento) y Resting (~0.5x,
acompaña una consolidación/continuación). Permite diferenciar "volumen que confirma entrada" de
"volumen que anticipa reversión" — algo que el sistema hoy no distingue explícitamente, y que el
curso marca como señal de alerta repetida (pico de volumen tras movimiento extendido = probable
giro en contra).

**Status:** evaluar.

---

## 3. Criterio posición vs. SMA 200 — de binario a régimen + estructura

Hoy es "por encima / por debajo" de la SMA 200. Dos mejoras candidatas:
- Ciclo de 4 etapas de Wyckoff/Weinstein (acumulación / tendencia alcista / distribución /
  tendencia bajista) como clasificación de régimen más rica que el binario actual.
- Estructura de pivotes (HPH/HPL para tendencia alcista, LPH/LPL para bajista) como criterio
  objetivo y verificable de que el swing va a favor de tendencia, en vez de depender solo de la
  posición relativa a la media.

Bonus relacionado: el curso destaca la EMA 200 en 60'/diario como la media más potente de todas
("rara vez se rompe sin reacción") — vale la pena evaluarla como nivel de referencia adicional a
la SMA 200 ya usada, no como reemplazo.

**Status:** evaluar.

---

## 4. Money management — límites de riesgo en capas

El R4 actual es un límite plano de pérdida máxima diaria (3%). El curso usa un esquema más
granular: máximo 2R de exposición simultánea (si dos posiciones abiertas ya suman 2R de riesgo,
no se abre una tercera sin mover stop a breakeven en alguna), 3R de pérdida diaria → parar el
día, 9R semanal → parar la semana, 12R mensual → dejar de operar con dinero real el resto del mes
y volver con medio lote la primera semana siguiente.

**Status:** evaluar — comparar rigor y practicidad contra el R4 actual antes de decidir si
reemplaza o complementa.

---

## 5. Money management — protocolo simétrico de toma de ganancias

Hoy el sistema define bien el límite de pérdida (R4) pero no tiene una regla equivalente para
cuando el día viene ganando. El curso insiste en no devolver ganancias ya conseguidas: metas
diarias/semanales/mensuales con reglas explícitas de qué hacer al alcanzarlas (parar, seguir
hasta perder 1 trade, seguir con medio riesgo, etc.).

**Status:** evaluar — es un gap real, no solo una mejora opcional.

---

## Notas

- Ninguno de estos puntos está codeado ni decidido. Son candidatos a evaluar, no compromisos.
- No bloquean el desarrollo del módulo 3BP/4BP (`spec_modulo_3bp_4bp.md`), que sigue su propio
  camino en paralelo.
- `Resumen Live Traders - Professional Trading Strategies.md` está subido en el proyecto
  (`docs/`) — fuente completa de contexto. Las secciones "Notas para nuestra estrategia" al final
  de cada parte tienen más detalle y más candidatos que no llegaron a esta lista priorizada.
