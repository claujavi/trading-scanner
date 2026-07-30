# Live Traders — Professional Trading Strategies
**Fuente:** Jared Wesley, Co-Founder Live Traders (curso "Professional Trading Strategies", 2018). Documento base para consulta y desarrollo de estrategias propias.

---

## Mapa del curso completo (13 capítulos)

1. **Introducción** — La verdad sobre el trading, por qué la gente fracasa, trading vs. gambling
2. **Candle Sticks & Trends** — Timeframes, lenguaje de velas, ciclos de mercado (4 etapas), 3 tendencias básicas
3. **Essential Patterns** — Setups de compra/venta, breakouts/breakdowns, flags, triángulos, 3/4 bar plays, turnaround play, parabólicos
4. **Pattern Boosters** — BT/TT, WRB/NRB, volumen +/-, EMAs, soporte, COC, RS/RW, MT, 50/100
5. **Gaps** — Tipos de gap, gaps pro vs. novato, rating de gaps (nivel 1-3), entradas en gap
6. **Super Plays** — Super 3BP/4BP, Super Curl
7. **Order Entry** — Tipos de orden, Level II, spreads, ECN routes y costos
8. **Money Management** — Reglas de cuenta, niveles de riesgo
9. **Trade Management** — BBB, Pivot, AON, MA, pyramiding, sell into strength
10. **The Business of Trading** — Plan de trading, registro de operaciones
11. **Psychology** — Por qué fracasan los traders, personalidad/tiempo/dinero/intangibles
12. **Pre-Market & Early Charts** — Cuándo esperar, lectura de pre-market
13. **Putting It All Together** — Rutina matutina, ejemplos, cierre

*(Índice completo — los 13 capítulos fueron resumidos en las Partes 1 a 11 de este documento.)*

---

## Parte 1: Introducción (Cap. 1, pág. 5-15)

### Idea central
El trading es un juego de **probabilidad estadística**, no de certezas. Un setup perfecto puede fallar y uno pobre puede funcionar. Lo que separa al trader rentable no es acertar siempre, sino la **consistencia**: operar cada día y cada trade de la misma manera, con un "edge" definido, y dejar que la gestión de dinero y de trade hagan el resto.

Recomendación explícita: elegir 1-2 estrategias/patrones, aplicar una gestión simple y repetir el proceso todos los días. El trader organizado y consistente gana dinero; el trader sobre-complicado e inconsistente termina abandonando por frustración.

### Por qué la mayoría fracasa
- Entran pensando que es fácil y que ganarán dinero rápido — expectativa poco realista.
- En la práctica toma **2-3 veces más tiempo** de lo que el trader cree para volverse rentable. Casi todos creen que serán la excepción; por definición, la mayoría no lo es.
- Copiar el estilo de otro trader no funciona: el enfoque personal debe surgir de la propia personalidad, algo que solo se aprende operando (experiencia real, muchos trades).
- La causa raíz del fracaso: no saber gestionar las emociones y dejar que las probabilidades jueguen a favor en el largo plazo.

### El gráfico como guía (no el ruido)
- Medios/noticias y "expertos" de TV tienen agenda propia, no son aliados del trader.
- El broker cobra por comisiones/fees, no por el resultado del trader.
- La mayoría de los "profesionales" (fondos, gestores) rinden por debajo del mercado.
- Hasta las blue chips pueden desplomarse.
- Conclusión: mantenerse objetivo, no dejar que el ego maneje las decisiones. El gráfico refleja el flujo real de dinero; la gente puede mentir (ej. Enron), el precio no.

### Técnico vs. Fundamental
- **Análisis técnico:** se apoya solo en el gráfico de velas (price action). No importan fundamentals (balance, management, P/E, noticias). El chart = flujo de dinero real.
- **Análisis fundamental:** analiza la empresa por dentro (finanzas, management, ratios).
- Postura del curso: el técnico es más simple, más específico, y al menos tan preciso como el fundamental — es el enfoque que enseñan.

### Trading NO es gambling
Toda operación técnica válida define **3 elementos antes de entrar**:
1. **Entry** (entrada)
2. **Stop** (freno de pérdida)
3. **Target** (objetivo de ganancia)

Sin los tres, no hay trade. Esto es lo que llaman *money management*: saber exactamente cuánto se arriesga antes de entrar. Ejemplo de la crisis 2008: la mayoría de los inversores fundamentales, sin stops definidos, vendieron en el piso tras perder 40-50%, justo antes de un rally alcista de 9 años. Un trader técnico con stop nunca deja que una posición caiga tanto — a esto lo llaman *"rule-based trading"*, superior al criterio discrecional del inversor promedio.

**Estructura Riesgo/Recompensa:**
- Target → orden límite (limit order)
- Entry → orden stop-límite (stop limit order)
- Stop → orden stop de mercado (stop market order)

Ejemplo del material: Entry $20.00, Stop $19.80 → riesgo $0.20/acción. Con 1.000 acciones = $200 de riesgo total.

Ejemplo de caso real (chart pág. 14): Entry $18.50, Stop $17.75, trade de 5 días con movimiento de $11.50 (+62%) — ilustran que el gráfico por sí solo dio entry/stop/target sin necesidad de leer noticias.

### Objetivo declarado del curso
Live Traders prioriza, en este orden de importancia real (aunque la mayoría de las escuelas de trading se enfocan solo en patrones de gráfico):
1. **Psicología**
2. **Money management**
3. **Trade management**
4. **Experiencia de mercado** (el factor que consideran más determinante)
5. Patrones de chart (importantes, pero menos de lo que se suele creer)

---

## Parte 2: Candle Sticks & Trends (Cap. 2, pág. 16-55)

### Timeframes y estilos de trading
- **Day-Trader / Scalper:** movimientos cortos dentro del día (5 min a 2 horas). "Income producing" — protege ganancias rápido, no da mucho margen de vuelta atrás, busca ingreso diario/semanal.
- **Swing-Trader:** movimientos de 1 a 15 días. "Wealth building" — da más margen para pullbacks y ganancias mayores, busca crecer el portfolio.
- **Core-Trader:** movimientos de semanas a meses. Da mucho margen y solo sale si se rompe la tendencia mayor (semanal/mensual).
- **Intra-day Swing Trading (enfoque propio de Live Traders):** híbrido — entran con timeframe chico para precisión de entrada, y si el stock se comporta bien durante el día, venden parte de la posición intradía (ingreso) y dejan el resto corriendo para swing (wealth building). Lo describen como "extremadamente poderoso".
- **Regla multi-timeframe:** siempre revisar al menos 2 (idealmente 3) timeframes por encima del timeframe de entrada, y 1 por debajo. Hay un TF de **BIAS** (el mayor, da el sesgo) y un TF de **ENTRY** (el menor, donde está el patrón).
- Clasificación por TF de entrada: 1'/2'/5'/15' = Intra-day Trader | 60'/Diario = Swing Trader | Semanal/Mensual = Core Trader. (No excluyente — se pueden combinar estilos).
- Ejemplos citados de la relación riesgo/recompensa lograda combinando timeframes: gap de nivel 1 con stop de $0.10 que corre $10 (100:1); breakout en 15' con stop de $0.70 que corre $20 en el diario (28:1). El caso destacado como "el tipo de trade más poderoso que se puede conseguir": un breakout en 2' alineado con un breakout en el gráfico diario — permite vender parte intradía y dejar correr el resto como swing con protección.

### Candlestick japonesas: las 3 claves de lectura
El curso usa exclusivamente velas japonesas (no barras "western", HLC ni OHLC). Toda vela tiene: open, close, high, low, cuerpo (bar body) y rango total. Vela verde = presión compradora creciendo (bullish); vela roja = presión vendedora creciendo (bearish).

Para leer una vela correctamente hay que mirar 3 cosas en conjunto (ninguna sirve aislada):
1. **Cómo se formó la vela** — "mirar adentro" bajando a un timeframe menor. Se prefieren velas **"battle tested"** (que muestran pelea/rechazo entre compradores y vendedores antes de definirse) por sobre velas que suben o bajan en línea recta sin resistencia.
2. **Dónde se formó** — una vela solo tiene significado según el contexto del gráfico (soporte, resistencia, zona de la tendencia).
3. **Cómo llegó hasta ahí** — la misma vela puede significar cosas distintas si es "igniting" (inicia un movimiento nuevo) o "ending" (lo agota/termina).

Términos introducidos aquí y que se desarrollan en el Cap. 4 (Pattern Boosters): **BT** (Battle Tested), **TT** (Trend Terminating), **WRB +/-** (Wide Range Bar, vela de rango amplio), **NBB** (Narrow Body Bar, vela de cuerpo angosto).

### Las 4 etapas del mercado (Wyckoff / Stan Weinstein)
Base de todo el curso — se repiten en cualquier timeframe (desde 1' hasta mensual):
- **Stage 1 — Acumulación / Apatía:** lateral, rango angosto, bajo volumen, poco interés.
- **Stage 2 — Demanda / Codicia:** tendencia alcista, rango amplio, volumen en aumento, "todos ganan plata".
- **Stage 3 — Distribución / Ansiedad:** lateral, tira y afloje entre compradores y vendedores, rango más errático; los compradores terminan cediendo el control.
- **Stage 4 — Oferta / Miedo:** tendencia bajista, generalmente el tramo más rápido del ciclo (el miedo pesa más que la codicia en el mercado).
- El ciclo va siempre 1→2→3→4→1 en orden, sin saltarse etapas — es la base de todo el análisis técnico que enseña el curso.

### Formación de techos y pisos (en stage 1 y stage 3)
- **V-Top / V-Bottom**, **M-Top / W-Bottom**, **Consolidation Bottom** (no suele haber "consolidation tops" porque el stage 3 tiende a ser errático por el tira y afloje).
- Regla clave: cómo llega el stock a la zona importa tanto como la zona en sí. Conviene esperar confirmación extra antes de entrar, o abrir con lote parcial y agregar con más confirmación.
- Los W-bottoms son más confiables después de movimientos muy extendidos, con vela final de rango amplio, volumen creciente en el cierre, e idealmente con estructura BT (battle tested).

### Las 3 tendencias
- **Uptrend:** máximos y mínimos de pivote cada vez más altos (HPH / HPL).
- **Downtrend:** máximos y mínimos de pivote cada vez más bajos (LPH / LPL).
- **Sideways:** máximos y mínimos de pivote iguales (EPH / EPL).
- Las tendencias direccionales (up/down) son más fáciles de explotar que las laterales, por definición "no direccionales". Regla práctica: mejor esperar que el precio rompa el rango lateral y comprar el primer pullback sobre el nuevo soporte, en vez de operar dentro del rango mismo.

---

## Parte 3: Essential Patterns (Cap. 3, pág. 56-113)

### Introducción: bias + entry
La lógica del capítulo: primero se busca el **bias** (sesgo direccional, largo o corto) en un timeframe mayor donde está "la plata grande"; ese sesgo por sí solo no alcanza para operar, así que se baja a un timeframe menor a buscar una **entrada concreta** con buen ratio riesgo/recompensa usando uno de estos "Essential Patterns". Recomendación explícita (igual que en la Parte 1): elegir solo 1-2 patrones al principio y dominarlos, no intentar usarlos todos.

Catálogo completo (mismos patrones, invertidos, para largos y cortos):
- Buy/Sell Set-Up (BS/SS), Retest Buy/Sell Set-Up (RBS/RSS), W-Bottom/M-Top (WBS/MSS)
- +3BP/-3BP, +4BP/-4BP (3 y 4 Bar Play)
- Breakout/Breakdown (BO/BD)
- Bull/Bear Flag (Wedge), Bull/Bear Triangle
- Turnaround Play (+/-)
- Parabolic Sell / Parabolic Buy (contra-tendencia)

### Buy Set-Up (BS) / Sell Set-Up (SS)
El patrón de continuación de tendencia más básico. Requisitos para un BS (long):
1. Debe estar en tendencia alcista de stage 2, o viniendo de un doble piso/transición (patrón W).
2. 2 o más máximos decrecientes (Lower Highs).
3. Pullback "secuencial" con menos de 50% de superposición (overlap) entre velas — ángulo de retroceso ideal de 45°, ni muy plano ni muy empinado.
Entrada: comprar cuando la vela siguiente rompe el máximo de la última vela del pullback; stop debajo del mínimo de esa vela. (Para SS/short es el espejo: tendencia bajista o M-top, Higher Lows, short al romper el mínimo).
Variantes: **Retest Buy/Sell Set-Up (RBS/RSS)** — el mismo patrón pero en un re-test de una zona ya probada. **W-Bottom / M-Top Set-Up (WBS/MSS)**, también llamado **"Transitionary Buy/Sell Set-Up (TBS)"** — funciona mejor tras un movimiento muy extendido con volumen creciente en el piso/techo.
Ejemplos del material logran R:R de 3:1 o mejor.

### Breakouts (BO) & Breakdowns (BD)
Definición: movimiento rápido de precio que atraviesa un nivel de soporte/resistencia, siempre a favor de la tendencia/movimiento existente. Pueden ocurrir en cualquier momento del día; los breakouts de mediodía (lunch time) tienden a tener menos continuidad, por lo que conviene subir uno o dos timeframes para confirmar compromiso. Nota práctica: son difíciles de "llenar" (fill) porque suelen saltar fuerte sin dejar mucho volumen disponible cerca del precio de entrada — conviene manejar nociones básicas de Level II.

**Checklist de 8 criterios para validar un breakout/breakdown:**
1. Consolidación "prolija" y ajustada, no errática — test práctico: ¿se puede trazar una regla recta arriba/abajo de la base?
2. Consolidando cerca de la EMA 9 o 21 (no hace falta tocarla, alcanza con ~70% de cercanía).
3. Volumen decreciente en la mitad de la base.
4. Precio en o cerca del máximo/mínimo del día (los breakouts a mitad de rango sirven, pero los de HOD/LOD son mejores).
5. Preferentemente en un número entero o medio (ej. $50.00 o $50.50) — no es requisito, es preferencia.
6. Volumen grande (3-5x lo normal) en el precio de entrada — muestra compromiso real; si se supera un volumen grande de compradores/vendedores, esos ya no estarán ahí para vender/comprar en contra más tarde.
7. Preferible una vela de "shakeout" (sacudida), posiblemente dejando un BT/TT.
8. Que haya "vacío" (void) arriba/abajo — sin resistencia/soporte cercano que frene el movimiento.

### Flags & Triangles
- **Bull Flag / Wedge:** 2+ máximos decrecientes en forma suave junto con 2+ mínimos crecientes — forma de "V" acostada o signo ">". Entrada: al romper el máximo de pivote previo, stop en el mínimo de pivote más reciente.
- **Bull Triangle:** techo plano con múltiples mínimos crecientes debajo (se parece a una base). Entrada: al romper por encima de la base, stop en el mínimo de pivote más reciente.
- Criterio inverso para las versiones bajistas (Bear Flag/Triangle).

### 3 & 4 Bar Plays (3BP / 4BP)
Patrón mecánico y muy preciso:
1. **Barra 1** debe ser una vela de rango amplio (WRB, el doble del tamaño promedio) que **inicia** el movimiento (1ª o 2ª vela del impulso). El volumen alto ayuda pero no es obligatorio.
2. **Barra 2 (y 3 en el 4BP)** deben ubicarse en el 50% superior del rango de la Barra 1, con máximos relativamente iguales entre sí.
3. La barra siguiente (3 o 4) es la **barra gatillo** (entrada y expansión); el stop va debajo de la barra más baja del grupo (2 o 3). El color de las barras intermedias no importa.
Versión bajista (-3BP/-4BP): espejo, barras en el 50% inferior con mínimos iguales.
Advertencia práctica: un pico de volumen después de varias velas en contra suele anticipar una reversión — señal de salir de la posición.

### Turnaround Bars (velas de giro)
También llamadas "engulfing bars". Para ser una vela de giro válida debe ser de rango amplio (el doble o más que las velas alrededor). Dos tipos:
- **Trend Changing:** termina la tendencia vigente y empuja el precio en la dirección contraria. Más efectivas después de un movimiento de varias velas cerca de un soporte/resistencia, con mucho volumen entrando al final.
- **Trend Confirming:** reconfirma la fuerza o debilidad ya existente de la tendencia, dando más fiabilidad a la operación.
Entrada típica por encima/debajo del extremo de la vela de giro, con stop en el otro extremo (suele ser un stop ancho). Si aparece una vela de "descanso" después que no rompe ese extremo, se puede usar el mínimo/máximo de esa vela como stop más ajustado.
Combinación destacada como especialmente potente: **vela de giro + 3 Bar Play** en el mismo punto.

### Parabolic Buy & Sell Set-Up (contra-tendencia)
A diferencia de todo lo anterior, este patrón opera **en contra** de la tendencia vigente, buscando aprovechar un desequilibrio extremo (capitulación de miedo o codicia) que suele revertir. Por su naturaleza son operaciones muy volátiles y "whippy" (erráticas), con mayor dificultad de fill y mayor riesgo de slippage en el stop. Es habitual necesitar un segundo intento de entrada tras ser sacudido (shaken out) la primera vez — no operar este patrón sin estar dispuesto a reintentar.

Requisitos:
1. 3 o más velas, con al menos 2 de rango **súper amplio** (2-3 veces el tamaño promedio — "las velas más grandes que hayas visto en esa acción").
2. Volumen **masivo**, no solo alto: mínimo 5x el volumen normal del período.
3. Lejos de la EMA 21 y todavía acelerando (idealmente 3-5% o más de distancia).
4. Una mecha de rechazo (bottoming/topping tail) o vela de rango angosto en el extremo.
5. La vela que marca el extremo (mínimo o máximo) debería tener el volumen más alto de todas — indica que todos los que querían entrar/salir ya lo hicieron.
Debe verse como una "cascada" (waterfall) — si no genera un "wow", no es parabólico. Los targets suelen ser un retroceso del 50% o la EMA 21; el R:R típico es más discreto, alrededor de 2:1.

---

## Parte 4: Pattern Boosters (Cap. 4, pág. 114-186)

### Concepto central
No todos los trades son iguales. Live Traders se define como "trader de probabilidades": ante cualquier patrón básico (hay miles por día), la calidad se mide por la cantidad de **"pattern boosters"** que acumula — atributos que hacen más confiable la operación. Cuantos más boosters confluyen, más alta la probabilidad de éxito. Dan **peso extra** a los boosters de "ubicación": soporte, niveles de retroceso y medias móviles. Son 10 boosters en total:

### 1. Bottoming Tails (BT) & Topping Tails (TT)
Una mecha de rechazo en el piso (BT) o techo (TT) indica que la oferta o demanda está creciendo — reversión probable cerca. Más confiables después de varias velas en una dirección, con volumen creciente y en zona de soporte/resistencia. Para ser una BT/TT "verdadera", la mecha debe ser al menos el 50% del tamaño total de la vela (pueden darse en velas WRB, ARB o NRB). Dentro de una base de consolidación, a estas velas se las llama **"shakeout bars"** (sacudidas).

### 2. Narrow Range Bars (NRB) & Narrow Body Bars (NBB)
Indican que la oferta o demanda está **disminuyendo** — reversión probable cerca (lo opuesto/complementario a BT/TT). NRB verdadera: rango 50% o menor al promedio. NBB verdadera: cuerpo 50% o menor al promedio del cuerpo. Igual que BT/TT, son más confiables tras varias velas en una dirección, con volumen y en soporte. Nota práctica: en acciones "spready" (con spread amplio), conviene dar más margen al stop cuando se opera con NBB por el riesgo de slippage.

### 3. Change of Color Bars (+COC / -COC)
Vela que indica un cambio de control **antes** de que el patrón dispare la entrada. +COC = los vendedores empiezan a ceder el control a los compradores. -COC = lo inverso. Son relevantes porque permiten anticipar quién está tomando el control antes de arriesgar dinero. **Importante: una vela COC NO es una vela de entrada** — se espera a que la vela siguiente rompa el extremo correspondiente para recién entrar.

### 4. Volumen: Igniting (IV), Ending (EV), Resting (RV)
El volumen indica el nivel de compromiso y ayuda a anticipar la próxima dirección. Nota clave repetida en todo el capítulo: **un pico de volumen después de un movimiento extendido (multi-vela) suele anticipar un cambio de dirección.**
- **Igniting Volume (IV):** inicia un movimiento nuevo (al menos el doble del volumen promedio).
- **Ending Volume (EV):** termina un movimiento (al menos el doble del promedio).
- **Resting Volume (RV):** acompaña la continuación/consolidación de un movimiento (~mitad del promedio).
El mismo pico de volumen puede ser "igniting" o "ending" según en qué parte del movimiento aparece: al principio de un tramo nuevo (igniting) o al final de uno extendido (ending).

### 5. Soporte y Resistencia: Nivel 1 y Nivel 2 (1S/1R, 2S/2R)
Basado en que el precio pasado predice zonas donde es probable que vuelva a reaccionar.
- **Nivel 1 (1S/1R):** zonas de transición entre etapas del mercado, generalmente retrocesos del **100%** a un pivote previo. Para contar como "Nivel 1" necesita **al menos un re-test** confirmado.
- **Nivel 2 (2S/2R):** zona preferida de pullback en tendencias establecidas (stage 2 o 4), generalmente retrocesos del **50%** al pivote previo.
- Regla clave: **"el piso roto se convierte en techo"** y viceversa ("the floor becomes the ceiling").
- También existe soporte/resistencia "genérico" (ni Nivel 1 ni 2) — por ejemplo una vela engulfing o un simple re-test reciente sin la extensión necesaria para ser Nivel 1.

### 6. Niveles de retroceso (50% y 100%)
Cuánto retrocede una acción indica si va a continuar en su dirección original.
- **50%:** el retroceso preferido en pullbacks dentro de una tendencia — señal de que la tendencia sigue vigente.
- **100%:** indica que la tendencia no era tan fuerte/débil como se pensaba, y que probablemente el precio vaya lateral o cambie de dirección — **excepto** si se trata de un re-test de una zona ya extendida con volumen creciente (ahí sí puede ser señal de transición válida, ver Nivel 1).
- El 50% es un **área aproximada**, no un número exacto.

### 7. Relative Strength (RS) & Relative Weakness (RW)
Compara la acción contra el mercado (SPY y/o QQQ). RS = la acción sube mientras el mercado está lateral o cae. RW = la acción cae mientras el mercado sube. Postura del curso: si el patrón y el gap son realmente excelentes, **operan la acción igual, aunque vaya contra el mercado**, cuando la RS/RW es extrema.

### 8. Medias móviles (EMA 9, 21, 200)
Live Traders no es fanático de los indicadores en general — el precio y el volumen son los focos principales. Las EMAs son indicadores **rezagados** (el precio ocurre antes que el indicador se forme), por lo que **no son soporte/resistencia real**, son más útiles como guía de tendencia y gestión.
- **EMA 9:** solo en timeframes cortos (1', 2', 5').
- **EMA 21:** se usa en todos los timeframes.
- **EMA 200:** timeframes altos (60', diario, semanal) — es, por lejos, la más potente; rara vez se rompe sin alguna reacción del precio. Los traders más experimentados casi no ponen medias en el gráfico, salvo la EMA 200 en timeframe alto.

### 9. Multiple Timeframes in Alignment (MTFA)
Regla de oro: **nunca operar en el vacío** (nunca mirar un solo timeframe). Conviene revisar al menos 2-3 timeframes antes de operar. Categorías: **Bias** = timeframe mayor (da el sesgo direccional) y **Entry** = timeframe menor (donde aparece el patrón concreto). 4 razones para usar MTFA: entradas más confiables con confirmación del TF mayor; bajar de TF para conseguir mejor entrada dentro de una tendencia ya establecida en el TF mayor; evitar operaciones malas por problemas en el TF mayor; ayudar a fijar objetivos de precio según el TF mayor. Dato práctico: la **falla de un patrón en el TF menor puede señalar la entrada correcta en el TF mayor** (ej. un Sell Set-Up de 2' que falla puede anticipar un Buy Set-Up de 15').

### 10. Market Timing (MT)
Aproximadamente el 75% de las acciones se mueven en la misma dirección que el mercado general (SPY/QQQ), por lo que conviene sincronizar el timing de las operaciones con el índice. 5 categorías de mercado:
- Fuerza extrema (subiendo en línea recta) → **nunca operar en contra**.
- Fuerza menor (subiendo lento) → RW aceptable.
- Lateral/errático → tanto RS como RW aceptables.
- Debilidad menor (bajando lento) → RS aceptable.
- Debilidad extrema (cayendo en línea recta) → **nunca operar en contra**, salvo que sea un movimiento parabólico (ver setups parabólicos, Parte 3).

### Combinando los boosters
Las últimas páginas muestran ejemplos reales donde confluyen varios boosters a la vez (ej.: BT + NBB + COC + retroceso del 50% + EMA 21 + MTFA + Market Timing) — el mensaje es que cuantos más boosters coincidan en el mismo punto de entrada, más alta la calidad ("odds") del trade.

---

## Parte 5: Gaps (Cap. 5, pág. 187-222)

### Qué es un gap
Diferencia de precio entre el cierre de ayer y la apertura de hoy. Casi todas las acciones gapean algo cada día, pero no todos los gaps son **"compelling"** (contundentes): para ser relevantes deben generar shock o crear un vacío (void). Los gaps son clave para el day trading porque las acciones que gapean suelen estar "en su propia página" — poco correlacionadas con el mercado general ese día.

La causa principal de un gap suele ser algún tipo de noticia (earnings, rumores de compra, aprobación de la FDA, upgrade/downgrade, una posición grande de un inversor reconocido, etc.). Regla del curso: **no importa por qué gapea la acción, solo importa que está gapeando.** La única excepción real es un buyout totalmente en efectivo (ahí no queda upside que operar); los ex-dividendos sí suelen ser operables. También operan ADRs (acciones extranjeras que cotizan en EE.UU.) caso por caso.

### Dos categorías principales de gap
- **Professional Igniting (PG):** cambian la dirección de largo plazo de la acción, generalmente gapeando **en contra** de la tendencia vigente (aunque a veces puede ser a favor de una tendencia todavía no extendida). Suelen "atrapar" (squeeze) a quienes estaban posicionados en la dirección contraria.
- **Novice Ending (NG):** también cambian la dirección, pero gapeando **a favor** de una tendencia ya extendida — típicamente marcando el agotamiento de esa tendencia (mismo concepto que la "Ending Volume" de la Parte 4).

### Gap excesivo (EG) — no operar
Un gap puede ser demasiado grande para el precio de la acción y arruinar la relación riesgo/recompensa. Ejemplo del material: un gap del 22% en una acción de $76 se considera excesivo y se descarta. El tamaño porcentual por sí solo no define qué es "excesivo" — depende del precio de la acción (ver Comentarios Generales más abajo).

### 6 preguntas para evaluar cualquier gap
1. ¿Hacia dónde gapea la acción?
2. ¿Desde dónde gapea?
3. ¿Tiene "valor de shock"?
4. ¿Gapea lo justo y necesario para superar un soporte/resistencia relevante, o gapea de forma excesiva y arruina el R:R?
5. ¿Gapea hacia un vacío (void) o hacia una resistencia?
6. ¿Muestra fuerza o debilidad relativa frente al mercado? (suele volverlo más potente)

### Rating de gaps: Nivel 1, 2 y 3
Sistema de calificación —mismo espíritu que los "pattern boosters" del capítulo anterior— para priorizar qué gaps operar primero en la apertura:
- **Nivel 1 (el más fuerte):** gapea sobre una o más velas de rango amplio (3-5%+) en contra; sobre 2 o más pivotes/una consolidación; lo justo y necesario para superarlos; hacia un vacío con espacio para moverse; con fuerza relativa en pre-market.
- **Nivel 2:** gapea sobre una vela roja "promedio" o una vela verde chica; sobre 1 o más pivotes; puede gapear un poco más de lo necesario; hacia un vacío; con fuerza relativa en pre-market.
- **Nivel 3 (el más débil):** gapea desde una vela verde (no de rango amplio); sobre 1 pivote o ninguno; gapea más de lo necesario (afectando el R:R); hacia un vacío pequeño; sin fuerza relativa frente al mercado.
- Se admiten matices "+"/"-" cuando un gap está cerca de un nivel pero le falta o sobra algún detalle menor (ej. "Nivel 1-" o "Nivel 2+").

### Entradas según el nivel del gap
Regla general: cuanto mejor el gap, más agresiva puede ser la entrada; cuanto más débil, más paciencia y confirmación hace falta.
- **Nivel 1:** entrada inmediata en la apertura (si el pre-market se ve bien); ruptura del máximo/mínimo de la primera vela de 1' (con cuidado, es fácil que sacuda la posición); patrones de 1' (3BP, BS, Turnaround Bar).
- **Nivel 2:** esperar 2-5 minutos antes de entrar; patrones en 2' o 5' (3BP, BS, Turnaround Bar); preferir al menos 2 velas formadas antes de entrar.
- **Nivel 3:** no operar antes de las 9:45am (necesita confirmación extra); preferir gráfico de 5' (un 2' de alta calidad también sirve); conviene esperar un re-test o una segunda señal de fuerza; después de las 9:45am, en 5', cualquier setup de calidad ya es válido.

### Comentarios generales (matices importantes)
- Noticia positiva no garantiza gap alcista, ni noticia negativa gap bajista.
- No todo gap alcista es "alcista de verdad" ni todo gap bajista "bajista de verdad" — hay que leer el patrón completo, no solo la dirección del gap.
- Un gap grande (15-20%+) no es automáticamente "excesivo".
- Las acciones de menor precio suelen tolerar mejor gaps grandes en términos porcentuales que las de mayor precio: una acción de $60 gapeando $10 (16%) tiene menos chance de seguir subiendo que una de $6 gapeando $1 (% similar).
- Los primeros 5 minutos del día son naturalmente erráticos y "spready" incluso en gaps de Nivel 1 — tip del curso: operar agresivo en la apertura solo con gaps de Nivel 1, y aun así dar más margen al stop o entrar con posición parcial para absorber el slippage.
- El objetivo no es ser siempre agresivo, sino usar el tipo de entrada correcto para la calidad de cada gap.
- Recomiendan preparar y calificar la lista de gaps **antes** de la apertura, priorizados por nivel — "organización y foco son la clave".

---

## Parte 6: Super Plays (Cap. 6, pág. 223-240)

### Qué es un "Super Play"
El "pináculo del trading" según Live Traders: la combinación de **dos patrones esenciales separados** (de los vistos en la Parte 3) que se juntan en el mismo punto para formar un patrón compuesto mucho más potente y confiable que cualquiera de los dos por separado. No hace falta que además tenga todos los pattern boosters, un gap y RS/RW — pero cuantos más de esos atributos se sumen, mejor. Aun con un Super Play, se debe seguir la gestión de dinero y de trade habitual (dejarlo llegar al target según el plan, y no tomarlo si ya se alcanzó la pérdida máxima diaria).

Son operaciones que se pueden tomar en o cerca de la apertura del mercado **independientemente de lo que esté haciendo el mercado general** — juego de momentum puro, muchas veces con tal RS/RW que el mercado se vuelve casi irrelevante. Son algo más agresivas por la volatilidad/spread propios de la apertura, pero igual de efectivas que cualquier otro setup del curso. Requieren buen manejo de órdenes y lectura de Level II, porque suelen resolverse en los primeros 1-3 minutos de la apertura — y también llegan al target más rápido.

Dos Super Plays principales:
- **Turnaround Bar + 3 Bar Play = Super 3BP** (variante: Breakout + Turnaround Bar).
- **Gap + Buy Set-Up + Breakout = Super Curl** (variante: "Pullback Breakout").

### Super 3BP (Turnaround Bar + 3/4 Bar Play)
Combina una vela de giro (turnaround bar, ver Parte 3) con un 3 o 4 Bar Play inmediatamente después, en la misma zona. Ejemplos del material muestran tanto versión alcista como bajista, y una variante donde se **agregan acciones** (add) a medida que el patrón confirma, ajustando el stop hacia arriba. El ejemplo destacado como "Perfección" combina un gap de Nivel 1 (Parte 5) con un Super Play — la confluencia de las tres cosas (gap + 2 patrones esenciales) se presenta como el escenario ideal. También se muestra una versión "Trend Changing Super 4BP", donde un gap bajista extremo con sobre-extensión ("puke") hacia un nuevo mínimo hace el patrón de reversión posterior aún más potente.

### Super Curl (Gap + Buy Set-Up + Breakout)
Estructura: un gap (al alza o baja) que retrocede y consolida en un rango angosto, idealmente cerca de un soporte, con una sacudida (shakeout) o un re-test de doble piso. Criterios:
- Acción en tendencia que retrocede y consolida.
- Retrocede aproximadamente 50% hacia el soporte.
- Idealmente con shakeout o re-test.
- Entrada al romper por encima de la consolidación.

Gestión recomendada para el Super Curl:
1. Primer target en el máximo del día (HOD), segundo target en el próximo número entero o medio por encima del HOD.
2. Cuando la acción "se enrosca" (curls) y la EMA 9 queda por debajo del precio, usar un trailing stop en el timeframe elegido.
3. Alternativa: salida completa (All-Or-Nothing) en 2-3R.
Nota de refuerzo: si el VWAP queda por debajo del "curl" durante el retroceso, o justo por encima del precio de disparo, el breakout tiende a ser más potente.

Variante mostrada: **"Alternate Curl: Retest"** — en vez de entrar en la ruptura inicial, se espera un re-test posterior de la zona de consolidación para entrar con más confirmación.

---

## Parte 7: Order Entry (Cap. 7, pág. 241-300)

Capítulo puramente operativo/técnico (no de patrones): tipos de orden, lectura de Level II, cómo conseguir mejores fills y cómo funcionan las comisiones y rutas ECN.

### Tipos de orden y cuándo usar cada una
- **Market:** ejecuta al mejor precio disponible. Fill garantizado, precio NO garantizado. Usar solo cuando es imprescindible entrar/salir ya.
- **Limit:** compra/venta a un precio específico o mejor. Se usa para salir en el **target**, o para comprar en un pullback / vender en corto un rebote.
- **Stop (market):** se convierte en orden de mercado al tocar el precio de stop. **Siempre** debe usarse como stop loss protector.
- **Stop Limit:** se activa al tocar el precio de stop, pero solo ejecuta dentro de un rango de límite definido — no garantiza fill. **Debe usarse para todas las entradas**, y es el tipo recomendado para traders nuevos.

Regla mnemotécnica del curso: **Limit = targets, Stop Market = stop loss, Stop Limit = entradas.** Las órdenes market se reservan para emergencias, porque no dan control sobre el precio de fill y suelen costar más.

### Level II: qué es y por qué importa
Level I = info básica (symbol, bid/ask, open/close, volumen). Level II = detalle de bid/ask por ECN con la profundidad (cuántas acciones hay en cada nivel de precio) y el "Time & Sales" (prints en tiempo real). Entender Level II ayuda a: ubicar dónde están compradores y vendedores, ver el spread real, medir cuán "whippy" (errático) es el papel, conseguir mejores fills sin quedar "skipped" (sin ejecutar), calibrar la salida cerca del target si hay una orden grande bloqueando el precio, y operar de forma más eficiente entendiendo dónde está la competencia.

### Qué determina el ancho del stop limit
Factores a considerar antes de poner una orden: volumen del papel, precio del papel, spread/whip, tamaño del stop/R:R, cantidad de acciones necesarias, y cuán urgente es conseguir el fill.
- **Alta liquidez** (5-10M+ acciones/día): spread ajustado (1-2 centavos), poco whippy, stops más ajustados.
- **Baja liquidez** (menos de 1M acciones/día): spread amplio (5-30c+), muy whippy, stops más anchos.
- **Precio alto** ($75+): spread amplio (5-30c), muy whippy, stops de 30-50c+.
- **Precio bajo** ($1-$30): spread ajustado (1-5c), menos whippy, stops de 10-30c.

**Regla práctica para el tamaño del stop limit:** dividir el stop loss por 5 y sumar un par de centavos; ante la duda, siempre errar hacia un límite más ancho (la mayoría de los traders le dan muy poco margen a sus entradas). Ejemplo: stop de 50 centavos → límite de 10-15 centavos; stop de 16 centavos → límite de 3-5 centavos.

### Anticipar la entrada ("Anticipating")
Consiste en colocar la orden un poco antes de que el precio toque técnicamente el nivel de entrada (ej. entrar en $66.00 en vez de esperar la ruptura real en $66.01), para asegurarse el fill en zonas de mucho volumen disponible. Beneficios: fill prácticamente garantizado dentro del rango buscado, casi sin slippage, se elimina el "no fill", tamaño de posición exacto y conocido de antemano, y el target queda relativamente más cerca por el mejor precio de entrada.

**El riesgo central: el "Anticipation Stop Out".** El precio llena la orden, pero nunca llega a romper realmente el nivel técnico; retrocede y toca el stop sin que el patrón se haya confirmado nunca — se pierde 1R en un setup que técnicamente jamás se activó. El material muestra varios ejemplos reales de esto.

Tres variantes para anticipar, con sus contras:
1. Anticipar con la posición completa 1-2 centavos antes → mejor fill posible, pero mayor riesgo de "anticipation stop out".
2. Mitad de la posición anticipada + mitad en la entrada técnica real con límite → fill garantizado para la mitad, buen precio promedio, pero la segunda mitad puede no completarse.
3. Cronometrar el Level II para apretar el botón justo antes de la ruptura → mejor resultado posible, pero muy difícil de ejecutar y consume atención que podría usarse para escanear otras oportunidades.

### Cómo leer el Level II para decidir el timing
- **Balance de poder:** ask grande + bid chico = el papel "no está listo" para moverse; bid grande + ask chico = está "listo para saltar" (ready to pop).
- **Tamaño del spread:** determina si conviene arrancar la orden antes (ej. $50.99 en vez de $51.00) — típico en acciones de precio alto (GOOG, AAPL, AMZN).
- **Acciones disponibles en el nivel vs. tamaño necesario:** si se necesitan muchas acciones y hay poco volumen mostrado en el precio objetivo, conviene arrancar la orden antes.
- Cerca del target, conviene vigilar el Level II por si hay una orden grande de venta (block order) que pueda frenar el precio — puede justificar tomar el target un poco antes de lo planeado.

### Comisiones y rutas ECN
Frase de apertura del capítulo: *"era rentable antes de las comisiones, pero apenas empataba (o perdía) después de las comisiones"* — de ahí la importancia de entender los costos.

Tipos de costos:
- **Fees de plataforma/bróker:** de $0 a $500+/mes (datos de Level I/II, gestión de cuenta, etc.).
- **Comisiones:** fijas ($3-10 por operación) o por acción ($0.0005 a $1 por cada 100 acciones).
- **Fees de ECN** (Electronic Communication Network — sistema que conecta brokers y traders para operar directamente sin intermediario, regulado por la SEC como broker-dealer): van desde pagar $3 por cada 1.000 acciones hasta **recibir** créditos de $2.10 por cada 1.000. No todos los ECN son iguales en liquidez ni en costo; los más operados son ARCA, BATS, Direct Edge (EDGX) y NASDAQ.
- **SEC Section 31:** $13 por cada millón de dólares operados (~$0.000013 por acción) — más alto en acciones de precio elevado.

**Concepto clave: agregar vs. remover liquidez.** Una orden límite que "descansa" en el book (agrega liquidez) suele generar un crédito; una orden de mercado o un stop-limit que se ejecuta inmediatamente contra el book (remueve liquidez) suele generar un cargo. Ejemplo con ARCA: se paga 0.003 por remover liquidez, se cobra un crédito de 0.0021 por agregarla.

Comparación de 3 escenarios sobre 1.000 acciones: entrar y salir siempre con orden de mercado en ARCA cuesta $6; entrar con stop-limit en ARCA y salir con límite en ARCA cuesta solo $0.90; entrar con un ECN más barato (TRIM, $1.50) y salir con límite en ARCA termina en un **crédito neto de $0.60**. Escalado a 1.200 operaciones/año, la diferencia entre el peor y el mejor esquema puede representar un ahorro del 43% al 67% de los costos de ejecución — miles de dólares al año en cuentas activas.

Conclusión del capítulo: elegir mal el bróker o la ruta ECN puede costar miles de dólares por año, igual que salir siempre con órdenes de mercado en vez de límite. Aun así, **el objetivo principal siempre es conseguir un buen fill** — ahorrar centavos en la ruta ECN nunca debe ser la prioridad por sobre la calidad de la ejecución.

---

## Parte 8: Money Management & Trade Management (Cap. 8 y 9, pág. 301-352)

### Capítulo 8: Money Management

**Idea central:** "Trading es hacer dinero, no tener razón." Dos reglas simples de Live Traders: (1) ser objetivo y usar sentido común, y (2) respetar y proteger la cuenta — operar chico hasta ser consistente. Frase repetida como mantra: **"te ganás el derecho a subir el riesgo"**. Traders nuevos no deberían arriesgar más de $50 por operación (idealmente $10-30), sin importar el tamaño de la cuenta; subir el riesgo se decide por **resultados**, nunca por necesidad o urgencia financiera personal.

**Unidades de "Riesgo" (R):** R es el monto que se está dispuesto a perder en una operación si falla. Fórmula: (Entrada − Stop) = riesgo por acción; Riesgo total deseado ÷ riesgo por acción = tamaño de la posición. Ejemplo: entrada $50.00, stop $49.50 (50c), riesgo de $500 → 1.000 acciones; si el trade llega a $51.25, la ganancia es $1.250 = 2.5R.

Beneficios de mantener un R fijo por operación: pérdidas consistentes y predecibles (casi siempre son solo un puñado de trades muy malos los que arruinan a un trader); permite planificar cuántas pérdidas se pueden tolerar en un día; tranquilidad mental (todos los trades "valen" lo mismo, dejar que el batting average y el sharpe ratio hagan el trabajo); y evita que el "ego" apueste más en un trade puntual, algo que casi siempre termina mal. Aun así, se recomienda cierta flexibilidad: el stop puede ubicarse en una zona más ajustada (mejor R:R, menos margen) o más amplia (peor R:R, más margen) según cada trade — no hay una respuesta única, depende de la "expectativa" (tema que se retoma en el Cap. 9).

**Consideraciones de money management:**
- Determinar el nivel de riesgo según resultados, no por subjetividad.
- Traders experimentados: no arriesgar más del 1% de la cuenta por operación — day traders: 0.5% suele ser el máximo realista por las limitaciones de buying power; swing traders: 1% está bien si hay resultados probados en el tiempo.
- Preservación de capital ante todo: sin capital no hay más trading.
- Armar un plan de trading escrito con reglas específicas.
- Monitorear la exposición: pérdida máxima de 4-5R por día; no más de 4-5 posiciones abiertas simultáneas si los stops no se movieron o los targets no se alcanzaron; si se pierden 4-5R en el día, **cerrar todo sin excepciones** (alternativa: cerrar tras 3 pérdidas consecutivas); tener reglas equivalentes para drawdowns semanales y mensuales.
- Cuidado con los límites de poder de compra (buying power): el riesgo elegido debe permitir al menos 3 posiciones abiertas a la vez.
- Controlar el riesgo siempre con un **stop loss técnico**, usando órdenes stop de mercado (garantizan el fill, aunque no el precio exacto) — con cuidado extra en acciones de spread amplio o bajo volumen, donde el slippage en el stop puede ser significativo.
- Swing traders: limitar la exposición de capital para evitar margin calls de Regulation T y sobre-exposición a gaps en contra en una sola posición.

**Ejemplo concreto de reglas de riesgo (regla personal citada en el material, en primera persona):** nunca ceder más de 2R en una posición abierta, ni bajar de breakeven después de haber realizado una ganancia de 2R. Exposición simultánea máxima de 2R (si 2 posiciones abiertas ya suman 2R de riesgo, no se puede abrir una tercera hasta mover el stop a breakeven o mejor en alguna de las otras). Límites de pérdida acumulada: **3R en el día** → parar el resto del día y reevaluar; **9R en la semana** → parar el resto de la semana; **12R en el mes** → dejar de operar con dinero real el resto del mes, volver con medio lote la primera semana del mes siguiente, y recién retomar el riesgo normal si se recuperan 5R o más (si se pierde más, tomar una hora de coaching profesional).

**Gestión de ganancias (profit management):** metas diarias en dólares, realistas y del mismo tamaño o mayores que la pérdida máxima diaria permitida — con reglas para cuando se cumplen (parar directamente; seguir hasta perder 1 trade; seguir con la mitad del riesgo hasta perder 2 trades). Metas semanales (ej. si se cumple un miércoles, tomarse un fin de semana largo) y mensuales, mejor pensadas como porcentaje (ej. si la meta es $10.000, no dejar que las ganancias caigan por debajo de $8.000 en ningún momento del mes). El objetivo declarado es **no devolver ganancias ya conseguidas**.

**Por qué se respetan los stops:** el material ilustra con ejemplos reales (una caída del 52% en una acción tras un stop de swing no respetado, y capturas de un foro donde alguien "opera" sin plan y entra en pánico) el argumento central: sin un stop técnico definido de antemano, no es trading — es apuesta.

### Capítulo 9: Trade Management

**Por qué importa:** la gestión de la operación una vez adentro es, según el curso, una de las razones principales por las que la mayoría de los traders no logra ser rentable. No todos los trades funcionan, así que cuando uno sí funciona hay que aprovecharlo — pero la mayoría sale (escapa) apenas con una ganancia chica por miedo. El patrón típico y no deseado: dejar que las pérdidas tengan gran impacto en el resultado y que las ganancias tengan poco impacto, exactamente al revés de lo ideal. No existe un "santo grial" de gestión — cada trader es distinto, y quienes identifican objetivamente sus propios sesgos emocionales y eligen un estilo que complementa su personalidad (en vez de dejar que el ego opere) suelen ser los más exitosos.

**Todo gira en torno a la "expectativa":** antes de elegir un estilo conviene preguntarse qué se espera de cada trade, si esas expectativas van en línea con la propia estrategia, y conocerse (¿soy nervioso o relajado?, ¿tolero devolver ganancias apuntando a un target grande?, ¿tolero salir temprano y ver que el papel sigue subiendo?). Todo es "dar y tomar": no se puede maximizar ganancias y proteger completamente contra pérdidas a la vez. El método más rentable en el papel no siempre es el mejor método para cada persona en la práctica.

**Los 7 estilos principales de gestión:**
1. **AON (All Or Nothing):** "poner y olvidarse". Se define target (2R, un nivel del gráfico, o un límite de tiempo) y stop, se cargan ambas órdenes y no se tocan más. Termina en uno de 3 resultados: stop, target, o cierre a las 15:55 ET antes del cierre. Extremadamente simple; funciona bien para quienes tienden a vender demasiado pronto, aunque puede ser duro ver un trade llegar al 90% del camino al target y volver a tocar el stop. El material señala que la mayoría de los traders **no logra superar en resultados** al simple AON.
2. **BBB (Bar By Bar):** correr el stop debajo del mínimo de la vela anterior en el timeframe elegido, típicamente recién cuando el trade ya se movió 0.5R-1R a favor. Es "ciencia exacta" (el mínimo previo es un dato objetivo), aunque conviene dejar algo de margen (5-10 centavos según el papel, más en acciones caras/volátiles que en una acción de banco tradicional). En timeframes bajos tiende a proteger ganancias más que a maximizar el target — útil cerca de una zona de target.
3. **Pivot:** esperar a que se forme un pivote genuino (no una simple vela de reversión aislada) y recién ahí correr el stop debajo de ese pivote, dejando pasar al menos 1-2 velas de confirmación antes de mover el stop. Apunta a targets más grandes que BBB, pero con más probabilidad de devolver ganancias sustanciales en el camino — recomendado para traders pacientes y disciplinados.
4. **Moving Average (9EMA):** correr el stop siguiendo la EMA 9, con un margen de al menos 15% del stop original por detrás de la media (ej. stop de 50 centavos → al menos 8 centavos de margen respecto a la EMA). Más "manual" que BBB, mejor que BBB para targets grandes, pero generalmente peor que el manejo por pivotes. En movimientos muy rápidos (breakouts, 3 bar plays) la EMA queda rezagada y puede devolver ganancias si se sigue de forma estricta.
5. **Add & Reduce (pirámide):** agregar a una posición ganadora sin aumentar el riesgo total, subiendo el stop de forma que el riesgo neto de la posición combinada baje a cero, a la mitad, o se mantenga en el riesgo original. Requiere ser buen selector de acciones, reinvertir ganancias con disciplina psicológica, y agregar solo sobre patrones reconocibles. Los ejemplos del material muestran cómo agregar puede llegar a duplicar el resultado de un mismo movimiento de precio.
6. **Sell Into Strength:** vender directamente a mercado cuando el papel se vuelve parabólico o rompe con tanto entusiasmo que no hay pivotes ni BBB razonables para proteger ganancias sin devolver una porción grande. No debería usarse a diario — se reconoce por un pico extremo de volumen, una vela de rango 2-3x lo normal, y que esa vela aparezca después de un movimiento ya extendido.
7. **Combination/Hybrid:** dividir la posición en partes (mitades, tercios) y aplicar distintas gestiones a cada parte — por ejemplo asegurar una parte rápido y dejar correr el resto con un target mayor, o usar pivotes al principio y pasar a un BBB más ajustado al acercarse al target (ej. cambiar de pivote a BBB al llegar al 75% del camino). Es el enfoque que el curso considera más "balanceado", aunque tampoco hay una fórmula única.

**Qué determina el tamaño del target:** el estilo de gestión elegido, la cercanía a soporte/resistencia, la calidad de la tendencia (ubicación relativa, distancia entre pivotes, qué tan extendida está), el entorno general del mercado, la fuerza/debilidad relativa (RS/RW), y si el trade va a favor o en contra de la tendencia mayor — los trades a favor de tendencia suelen tener targets potenciales más grandes.

**Re-entrada tras un stop-out completo:** cuando un trade da stop completo y el precio vuelve exactamente al punto de entrada original, re-entrar con los mismos parámetros (mismo entry, mismo stop, mismo target) funciona, según la experiencia personal citada en el material, **"84% de las veces"** — no hace falta que haya un patrón nuevo formado. El propio material aclara explícitamente: no tomar esa cifra como un hecho, sino backtestear al menos 100-200 operaciones propias antes de aplicar la regla, porque las estadísticas personales pueden diferir.

**Conclusión:** no existe "el mejor" método — la pregunta correcta no es cuál da más plata, sino cuál se puede seguir de forma realista el 99% de las veces. No elegir un método que vaya en contra de la propia personalidad, ni uno que dependa de un batting average alto si no se es bueno eligiendo acciones, ni uno que dependa de un Sharpe alto si no se es paciente. Cierre del bloque completo (Cap. 8 + 9): sin los 3 pilares — auto-gestión (psicología), money management y trade management — es difícil tener éxito como trader; la auto-gestión es la base de los otros dos, porque sin poder gestionarse a uno mismo es imposible seguir un plan con consistencia.

---

## Parte 9: The Business of Trading & Psychology (Cap. 10 y 11, pág. 353-427)

### Capítulo 10: The Business of Trading

**Idea central:** la falta de preparación es una de las mayores causas de fracaso en trading. Advertencia explícita: no asumir que uno es diferente o mejor por haber tenido éxito en otro campo — "este negocio le enseñó humildad a todo tipo de persona imaginable". Ciclo de planificación recomendado: **Plan → Implementar → Medir → Evaluar → Mejorar**, en bucle continuo.

**El plan de trading** es un conjunto de reglas escritas que define cómo y cuándo se opera. Debe incluir: mercados a operar; gráficos/indicadores usados (desde semanal hasta 1'); reglas de cuenta y sizing (nivel de riesgo, drawdown máximo diario/semanal/mensual); reglas de entrada (filtros de horario, patrón, entorno, liquidez, spread); reglas de salida (targets, stops, salidas por tiempo); y educación continua (journaling, lectura, backtesting). El material incluye un plan de muestra completo con objetivos concretos (BA 50%, Sharpe 1.75-2.0, R:R 2:1, riesgo máximo 1% —idealmente 0.5%—, máximo 6 trades/día, límites de pérdida de 1R/trade, 3R/día, 9R/semana, 12R/mes con parada inmediata).

**Checklist de entrada de muestra (3/4 Bar Play):** exige un mínimo de **7 "must haves"** (vela igniting de rango amplio sobre un pivote significativo, bar 2 en el 30-50% superior del bar 1, sin reportes que puedan afectar el trade, R:R mínimo 2:1, a favor de la tendencia, restricción de timeframe según la hora del día, spread no más del 30% del stop, entre otros) y un mínimo de **3 "like to haves"** (volumen doble en la vela igniting, RS/RW, número redondo, etc.) antes de tomar el trade — formaliza la idea de "pattern boosters" de la Parte 4 como un filtro de aprobación/rechazo concreto.

**Rutina diaria de muestra:** pre-mercado (armar y calificar lista de gaps por nivel, revisar calendario económico y de earnings, definir sesgo de mercado, revisar el plan, visualizar el día); intradía ("ABS — Always Be Scanning", reglas por franja horaria: mañana máximo 4 trades enfocados en gaps favoritos, almuerzo máximo 1 trade subiendo a 15', tarde gráficos de 5'-15' con máximo 2 trades); cierre (asegurarse de estar flat, cargar todo en la planilla de tracking, journaling, listar fortalezas/debilidades a mejorar, preparar la watchlist del día siguiente, y dedicar 1-2 horas diarias a mejorar: leer, hablar con otro trader, backtestear, o directamente descansar).

**Diario de trading:** captura el proceso de pensamiento y el estado emocional durante cada trade, dividido en 3 secciones (ganadores, perdedores, y "otros" — trades que se quisieron tomar pero no se tomaron por miedo). Ejemplo real citado: vender la mitad de una posición antes de lo planeado por miedo a devolver una ganancia nunca antes vista, reconociendo que esa decisión costó 3R ($1.500) — y anotando como aprendizaje agregar una regla específica para movimientos de 5R o más.

**Planilla de tracking:** registro numérico y estadístico de todas las operaciones — permite ver qué funciona y qué no, con desgloses cruzados por dirección, timeframe, tipo de setup, hora de entrada, si se siguió el plan, día de la semana, tamaño de posición, minutos en el trade, precio de la acción, tamaño del stop, y si fue a favor o en contra del mercado, todo cruzado con batting average y sharpe ratio. Incluye también el seguimiento de la curva de equity.

**Backtesting:** tomar trades pasados para predecir el desempeño futuro (ej. comparar trailing con EMA 9 vs. pivotes, o targets de 2R vs. 3R). Es una simulación, no una garantía, pero es valiosa. Ejemplo real citado: comparando 8 métodos de gestión distintos sobre 80 trades en 1 mes, los resultados fueron de 19.34R (peor método) a 44.31R (mejor método) — el mismo criterio de entrada, solo cambiando el estilo de gestión, produjo una diferencia enorme en el resultado final.

**Expectativas realistas:** el trading suele tardar **2-3 veces más de lo esperado** en volverse rentable (si se planificaron 12 meses, probablemente tome 24-36). Comparar con cuánto tardó en volverse "bueno" en la profesión anterior (usualmente 5+ años) — no hay razón para esperar que el trading sea más rápido. Recomendaciones: tener una fuente de ingreso secundaria y no depender del trading durante los primeros 12-36 meses; esperar altibajos como algo normal; entender que se requiere trabajo duro, dedicación, persistencia, educación continua y experiencia real de mercado combinados.

**El costo real:** capital inicial de cuenta ($5.000-$250.000), equipo de oficina ($1.000-$5.000+), educación ($1.500-$5.000+), fees de plataforma y de operación ($200-$5.000+/mes), gastos de vida, y el costo de oportunidad del ingreso perdido mientras se aprende. Ejemplo de análisis con una cuenta de $50.000: el total del primer año (sin contar ingreso perdido) puede rondar los $125.000.

**Etapas del trader:** Trainee (simulador/paper trading, 1-4 semanas) → Beginner (dinero real, riesgo chico de $10-25) → Intermediate ($50-100 de riesgo hasta lograr consistencia durante varios meses) → Professional (se gana el derecho a arriesgar 1% en cuentas retail, hasta 2% en cuentas prop). Nota explícita: al principio **no** basar el riesgo en porcentaje de cuenta — eso es algo que solo los traders experimentados se ganaron el derecho de hacer.

**Share sizing por estilo:** distribución sugerida: Core 1.5% de la cuenta, Swing 1.0%, Intra-day 0.5%. Regla general para day traders activos: dividir el buying power por 1.000 como guía del riesgo máximo por trade (ej. $150.000 de BP = $150 de riesgo). Un ejercicio comparativo del material mostró que, pese a arriesgar menos por trade, el estilo intradía generó la mayor ganancia bruta total gracias a la frecuencia — más riesgo por trade no equivale a "más eficiente".

**Retail vs. Prop:** cuenta Retail necesita $30.000+ para no caer en restricciones de PDT (Pattern Day Trading), apalancamiento máximo 4:1, buen retorno de 10-20% mensual, sin límite al drawdown posible, generalmente sin rebates de comisión, permite mantener posiciones overnight. Cuenta Prop necesita tan poco como $3.000, apalancamiento 20:1+, buen retorno de 50% mensual (asumiendo 2% de riesgo), drawdown diario controlado por la firma, con rebates de comisión, pero generalmente no permite mantener posiciones overnight.

**"El tamaño no importa":** ejemplo real del propio fundador de Live Traders — una cuenta abierta con $2.165 que se convirtió en más de $51.000 en 12 meses, documentado con capturas trimestrales — ilustrando que no se necesita mucho capital para generar un ingreso significativo, siempre que haya paciencia, disciplina y money management consistente.

**Cierre del capítulo:** estadísticamente menos del 8% de la gente en EE.UU. gana $100K+/año, y en trading el número es aún menor. Comparado con otros negocios, los costos de entrada al trading son baratos. 10-20% de retorno mensual ya es un resultado muy bueno. Frase de cierre: **"no dejes que tus expectativas superen tu experiencia"**. Sobre la oficina: tratar el trading como un negocio real, no escatimar en computadora, monitores, internet y plataforma — el trader "es tan bueno como la confiabilidad de su plataforma, computadora y conexión a internet". Sugerencia de layout: pantalla principal con order entry/Level II y gráficos de entrada (2', 5', 15'); monitores auxiliares con gráficos de escaneo en todos los timeframes, listas de favoritos, miniaturas de la watchlist matutina (10-20 acciones), e indicadores de mercado (QQQ o SPY). Sugerencia final: **mantenerlo simple**.

### Capítulo 11: Psychology

**La verdad sobre el trading:** exige un nivel de autodisciplina y objetividad que no es necesario en ninguna otra profesión, porque no hay jefe ni cliente vigilando — uno es su propio "policía". No se sabe realmente cómo se va a reaccionar ante algo hasta enfrentarlo; hay que ser objetivo y honesto con uno mismo, y nunca hacerse la víctima.

**Por qué fracasan los traders (lista extensa del material):** no creer en uno mismo (autoimagen pobre); mala o nula planificación (no tratar el trading como un negocio); falta de disciplina — posiblemente la causa individual más grande de fracaso; falta de capital (extensión de la mala planificación); malas reglas de money management (exceder pérdidas máximas, no poder aceptar una pérdida); malas reglas de trade management (vender demasiado pronto, o usar un sistema que no se puede seguir); falta de objetividad por ego demasiado grande (no poder adaptarse a que el mercado cambia todos los días); falta de persistencia o pereza; expectativas que superan la experiencia (codicia e ingenuidad, timeline poco realista); el "juego de la culpa" — señalado como quizás lo más dañino de todo, porque el mercado no sabe quién es uno y no le importa; ser "consistentemente inconsistente" (la repetición es la base del aprendizaje); y ser un "globo de aire caliente" — dar buenos consejos a otros pero no poder seguirlos uno mismo.

**Por qué tienen éxito los traders:** se prepararon adecuadamente antes de empezar; tienen expectativas realistas; tienen reglas claramente definidas y rara vez las rompen; cuando encuentran una oportunidad de calidad, actúan; una vez iniciado el trade, dejan que el plan los guíe; si no encuentran una oportunidad de calidad, se quedan quietos (**"SOH" — sit on hands**); siempre miran el panorama mensual, no el diario; no cambian sus reglas sobre la marcha; son consistentes y honestos en su enfoque.

**Por qué luchan los traders aun siendo técnicamente buenos:** la mayoría logra proficiencia técnica (reconocer patrones, acertar la dirección, definir entrada/stop/target) pero subestima la psicología — **el 95% del trading es psicológico**. El "idiota" interior sabotea incluso a quien sabe exactamente qué hacer pero no lo hace; muchos son excelentes dando consejos a otros pero no pueden seguir su propio consejo.

**Concepciones erróneas comunes:** que no se puede quebrar tomando ganancias chicas (vender siempre demasiado pronto también arruina resultados); que el cambio real ocurre rápido; que el trading rentable es solo para los "afortunados"; que se puede copiar el camino al éxito sin invertir tiempo; que "se va a aprender del mercado" y por eso no hace falta educación; que el éxito pasado en otro campo da ventaja; que la gestión que da más "R" en el papel es automáticamente la que hay que usar, sin considerar si se ajusta a la propia personalidad; que copiar el estilo de otro trader exitoso (ej. un scalper) va a funcionar igual aunque sea opuesto a la personalidad propia. Mensaje central: el trading es "el gran igualador" — el mercado no sabe ni le importa quién es cada uno; el ego y la experiencia previa no dan ninguna ventaja.

**Cosas que hay que aceptar:** no se es perfecto; se va a perder dinero a veces; se tienen limitaciones y debilidades reales, aunque se elija negarlas; el ego no tiene lugar en este negocio; el éxito pasado en otro campo no tiene relación con el éxito futuro en trading; hay que admitir el problema específico (vender demasiado pronto, no tomar los stops, etc.), decidir conscientemente trabajar en corregirlo, y tener un plan de acción concreto; y hay que aceptar que si genuinamente no se disfruta esto, el éxito se va a escapar.

**Mindfulness:** la capacidad de estar consciente de los propios pensamientos, creencias y sesgos en tiempo real. El pensamiento y el estado de ánimo siguen a la emoción — la emoción **no** sigue al pensamiento. Las emociones se activan cuando se rompe un patrón familiar o establecido, lo que suele llevar a estrés → miedo → malas decisiones → mal trading → pérdida de dinero. Cita citada: *"Creamos nuestro entendimiento del mundo a partir de nuestras adaptaciones a nuestros miedos y deseos más profundos"* (Rande Howell). Hay que desarrollar mindfulness para examinar los propios pensamientos antes, durante y después de cada trade — de lo contrario se pierde la perspectiva objetiva y el proceso basado en el miedo se repite en el próximo trade.

**Cambiar las propias creencias:** uno se convierte en lo que más piensa — cuanto más se piensa en "no perder", más se pierde. Cambiar el sistema de creencias emocional es mucho más difícil de lo que se cree, y por eso la mayoría de los traders son muy predecibles. El cambio requiere examinar qué causó las reacciones previas (¿por qué hago lo que hago?) y "reinventarse" — algo que la mayoría de la gente nunca acepta del todo, viviendo en un estado de defensa y negación.

**Causa y efecto:** todo tiene una causa — hay que rastrear la cadena hasta el origen (ej.: si vendo demasiado pronto, ¿es porque tengo miedo de devolver ganancias? Si es así, ¿es porque "necesito" el dinero? Si necesito el dinero, ¿cómo resuelvo eso? — posibles soluciones: trabajo part-time, recortar gastos, vender algo de valor). A veces la respuesta no es lo que se quiere escuchar y puede requerir re-evaluar todo el proyecto de trading, incluyendo el timeline y los ahorros necesarios.

**Atributos de los traders exitosos:** objetividad y disciplina; deseo sincero de éxito con foco singular; disfrutan genuinamente lo que hacen; actitud positiva; sin creencias auto-limitantes; tienen un plan con rutina y metas paso a paso; visualizan y ensayan sus metas a diario; son responsables de todas sus acciones sin excusas; tienen consecuencias cuando rompen su propio plan; tienen expectativas realistas dado su experiencia; nunca se rinden. Frase de cierre: **"o lo querés lo suficiente, o no"**.

**Definiéndose a uno mismo (para elegir el estilo correcto):**
- Por personalidad: nervioso/inquieto → plazo corto (scalp/micro-scalp), targets chicos, BA alto, sharpe bajo, cómodo con stops ajustados y mayor frecuencia. Paciente/relajado → plazo largo (día completo o swing/core), targets grandes, BA bajo, sharpe alto, stops más anchos y menor frecuencia.
- Por tiempo disponible: todo el día → 5'/15' con pivotes (movimientos de 3R-5R). Medio día → 5' con AON o pivotes de TF chico (2R-4R). 1-2 horas → 2'/5' con AON chico o BBB/EMA 9 (1R-3R). Horas dispersas → diario/semanal, trader swing/core (5R+), escaneando de noche y revisando al día siguiente.
- Por restricciones de capital: cuenta PDT (+$25.000) permite trades ilimitados y mantener overnight, pero requiere más capital; cuenta retail limitada (-$25.000) permite abrir con poco dinero pero restringe a 4 trades cada 5 días; cuenta prop/fondo requiere poco capital inicial ($3K-$10K) con apalancamiento mucho mayor (20:1+), pero exige usar la plataforma de la firma y generalmente no permite overnight.
- Por intangibles: proficiencia técnica, capacidad de multitarea, capacidad de escaneo, experiencia previa, y cualidades individuales (dedicación, persistencia, tolerancia al riesgo, capacidad de adaptarse al cambio, objetividad).

**Cierre del capítulo (resumen de psicología de trading):** seguir soporte y resistencia da una ventaja estadística real, aunque a veces falle — son trades de mayor probabilidad, no garantías. Perder el miedo significa confiar en las probabilidades y vivir en el presente. La consistencia es lo más importante para el éxito. *"¿De qué sirve tener razón si no te pagan por eso?"* — hay que apuntar a perder poco y ganar mucho quando el trade va a favor. Se opera para hacer dinero, no para tener razón, ser un héroe o buscar una "descarga" — esto es un negocio serio, no un juego para apostadores. Escuchar lo que dice el mercado es el trabajo más importante — no imponerle las propias creencias, porque el mercado simplemente "es"; hay que adaptarse a él, no al revés. No hay secretos ni santo grial: entender y dominar las propias emociones es la clave del éxito. Reflexiones finales citadas: si no se está dispuesto a perder dinero en un trade específico, mejor no tomarlo; es mucho más difícil corregir malos hábitos ya arraigados que aprender bien desde el principio; solo se gana si no se le tiene miedo a perder; el trabajo del trader se resume en identificar su ventaja (edge), evaluar riesgo/recompensa y monitorear sus propias emociones; los buenos trades suelen "saltar a la vista" — si no es obvio, probablemente no sea una buena idea; la disciplina es simplemente hacer lo correcto en el momento correcto; y el trading es **99% esperar** por entradas y targets, y solo 1% acción — ese 99% del tiempo debería usarse para escanear y buscar oportunidades.

---

## Parte 10: Pre-Market & Early Charts (Cap. 12, pág. 428-449)

### Idea central
Capítulo corto, muy práctico, centrado en un solo mensaje: **revisar el gráfico de pre-market antes de la apertura cambia por completo qué entradas son posibles**. Sin esa información, muchos movimientos parecen "imposibles de operar" porque ya se ven extendidos al abrir el gráfico regular; con pre-market, se ve la base/consolidación completa y el punto de entrada real.

### Beneficios de usar gráficos de pre-market
- Ayuda a evitar acciones que probablemente retrocedan (pullback) apenas abra el mercado.
- Permite entrar más temprano de lo normal.
- Al entrar temprano se aprovecha el movimiento **completo**, no solo los pullbacks o consolidaciones ya extendidos que quedan visibles recién después de la apertura.
- Regla de tratamiento: el pre-market se trata como cualquier gráfico regular — **movimiento ya extendido = esperar** (pullback o consolidación); **movimiento no extendido = entrar de inmediato** (asumiendo que el gráfico diario también se ve bien).
- Se exige la misma calidad de patrón que en cualquier otro momento del día — nada de bajar el estándar solo porque es la apertura.
- Advertencia explícita: no "enamorarse" de un gap y querer entrar a cualquier costo sin haber revisado antes el gráfico de pre-market — es un juego peligroso.

### Desventajas de usar gráficos de pre-market
- El pre-market a veces no anticipa exactamente dónde terminará abriendo la acción.
- Entrar en los primeros 1-2 minutos es más difícil por spreads más amplios y a veces menor volumen.
- Los primeros minutos del día suelen ser más "whippy" (erráticos) que el resto de la sesión — más fácil ser sacudido (stop-out) rápido, con algo más de slippage de lo normal.
- Aun así, el material sostiene que las ventajas superan ampliamente estas desventajas — **siempre que se opere de forma metódica y sistemática, no al azar**: deben cumplirse patrón, volumen y demás criterios habituales, sin excepciones.

### Ejemplos reales (chart cases)
La mayor parte del capítulo son casos reales (CREE, TASR, PXD, OCLR, SRPT, ULTA, NFLX, DRI, OSTK) que ilustran el mismo punto una y otra vez: comparando el mismo gráfico "con" y "sin" datos de pre-market, sin esa información la base y el punto de entrada quedan invisibles y el movimiento parece "un stock totalmente distinto, sin entrada posible". Con la información completa, aparece una base o consolidación de pre-market clara, con entrada justo en la ruptura al abrir el mercado y stop debajo/encima de esa base.

Puntos remarcados en varios ejemplos:
- Muchas de estas operaciones se resuelven en minutos: casos citados de trades cerrados a los 4 minutos, o "sin ninguna entrada posible después de las 9:31am" — reforzando que sin preparación previa (favoritos ya identificados, niveles ya marcados) la ventana de entrada se pierde.
- **"Excessive Gap = Fade" / "Excessive Gap = Stay Away":** reafirma el criterio de la Parte 5 (Gaps) de que un gap demasiado grande arruina el R:R y no debe operarse de forma agresiva, aun con un buen patrón de pre-market.
- **"Focus on Favs":** operar solo sobre la lista de favoritos/watchlist ya preparada de antemano en la apertura — de lo contrario el trader se dispersa y pierde las mejores ideas del día (conecta directamente con la rutina de pre-mercado de la Parte 9).

### Cuándo esperar (When To Wait)
No todo gráfico de pre-market lleva a una entrada inmediata en 1' o 2'. Razones para esperar:
- No hay ninguna ventaja (edge) clara en el gráfico de pre-market.
- El gap no es "genial" y requiere más tiempo de confirmación (pensar en los gaps de Nivel 3 de la Parte 5).
- La acción es demasiado ilíquida para operarla temprano.
- El spread no es manejable (excesivo) en los primeros minutos.
- El patrón de pre-market nunca dispara una entrada temprana.

Qué se espera en esos casos: más confirmación, más volumen, un setup de probabilidad ligeramente mayor (potencialmente subiendo a 2' o 5'). Los **3 y 4 Bar Plays** se destacan como el patrón ideal para operar el momentum de la mañana temprano cuando conviene esperar un poco más antes de entrar.

---

## Parte 11 (final): Putting It All Together (Cap. 13, pág. 451-489) + Apéndice (pág. 490-525)

Último capítulo del curso — integra todo lo visto en los capítulos anteriores en una rutina operativa concreta, y cierra con un apéndice de referencia (glosario, lecturas, principios y planillas). Frase de apertura: *"Los traders experimentados controlan el riesgo, los inexpertos persiguen ganancias"* (Alan Farley).

### Rutina matutina (Morning Routine)
Checklist recomendado antes de operar: mentalidad adecuada y rituales matutinos; formular un **sesgo de mercado** (revisar QQQ o SPY y ubicar zonas de soporte/resistencia); escanear gaps contundentes desde el scanner de la plataforma ($ o % gainers/losers), la watchlist diaria y la lista de "carry over" de la noche anterior, sectores fuertes/débiles y el mapa de calor del NASDAQ; clasificar los gaps por nivel (según las reglas de la Parte 5); poner los favoritos en gráficos miniatura ordenados por prioridad; desarrollar una estrategia para operar esos favoritos (gaps/plays de Nivel 1); chequear el horario de los reportes económicos relevantes; y **enfocarse y operar solo lo que está en la watchlist**.

### Sesgo de mercado: qué priorizar según el gap
Cinco escenarios según cómo gapea el mercado general (SPY/QQQ), cada uno con su foco recomendado:
1. Mercado gapea al alza de forma extendida o hacia resistencia → foco en gaps de relative weakness y gap ups extendidos.
2. Mercado gapea al alza sin extenderse, con espacio para subir → foco en los "Top Long Watches" (gaps Nivel 1 y 2).
3. Mercado gapea neutral → foco en gaps Nivel 1, RS/RW y los favoritos diarios habituales.
4. Mercado gapea a la baja sin extenderse, con espacio para bajar → foco en los "Top Short Watches" (gaps Nivel 1 y 2).
5. Mercado gapea a la baja de forma extendida o hacia soporte → foco en gaps de relative strength y gap downs extendidos.

Nota importante: por la naturaleza de operar la apertura vía gaps, el sesgo de mercado general pesa **menos** de lo habitual en esos primeros minutos — se está aprovechando el momentum propio del gap y del gráfico de pre-market, no necesariamente la dirección del índice.

### Comentarios generales sobre gaps de mercado
Tratar los "gaps de mercado" (del SPY/QQQ) con las mismas preguntas que un gap de una acción individual: extensión, vacío (void), valor de shock. Algunos gaps de mercado son claros y precisos; otros son vagos y no ofrecen una lectura clara — en ese caso hay que apoyarse en gaps sólidos de Nivel 1 y RS/RW combinados con un buen gráfico de pre-market para justificar una entrada temprana. Recordatorio: sin importar la hora del día, siempre exigir calidad — "no somos apostadores, somos traders de patrones que usamos los gráficos para inclinar las probabilidades a nuestro favor", algo especialmente importante en la apertura. El sesgo de mercado y la preparación de pre-mercado pueden tener un impacto muy fuerte en el resultado del día.

### Calendario económico y claves del escaneo de gaps
La mayoría de los datos económicos no afecta significativamente los primeros 30 minutos de la sesión, pero sí puede afectar el trading después de las 10am. Sobre el escaneo: **"si no sos un buen scanner, probablemente nunca serás un buen trader"** — hay que saber exactamente qué se está buscando, porque no se puede encontrar algo si no se sabe cómo se ve. Opciones de escaneo: $ gainers/losers, % gainers/losers (suelen encontrar acciones de menor precio), mapa de calor del NASDAQ, lista de carry-over, watchlist diaria, ideas del chat room y newsletter de Live Traders. El volumen en el pre-market scanning indica compromiso: las acciones con mucho volumen de pre-market tienden a moverse más, aunque esto no significa descartar gaps con menor volumen de entrada.

### Evaluar cada gap (mismas 6 preguntas de la Parte 5)
¿Hacia dónde gapea? ¿Desde dónde gapea? ¿Tiene valor de shock? ¿Gapea lo justo para superar soporte/resistencia o de forma excesiva (arruinando el R:R)? ¿Gapea hacia un vacío o hacia una resistencia? ¿Muestra fuerza/debilidad relativa frente al mercado (la vuelve más potente)?

### Thumbnail charts, favoritos y ejemplos de "scan, watch, wait, execute"
Se arman gráficos miniatura con los favoritos numerados por prioridad (#1, #2, etc.), cruzando ideas propias con las del chat room. Se insiste en **"Focus on your Favs"**: operar solo la lista de favoritos preparada de antemano o el trader se dispersa y pierde las mejores ideas (mismo punto ya visto en la Parte 10). Varios ejemplos reales ilustran el proceso completo escanear → vigilar → esperar → ejecutar, incluyendo un caso paso a paso con la acción POWR: se detecta en el scanner de pre-market gainers, se agrega a la watchlist de miniaturas, se vigila su Level II de pre-market, y se ejecuta la entrada sobre $9.00 apenas abre el mercado (con stop $8.80 debajo de la base de pre-market) — la acción llegó a $9.84 y no hubo ninguna otra oportunidad de entrada después de ese primer movimiento.

### El proceso resumido ("Putting It All Together")
Los cuatro pasos que sintetizan todo el curso:
1. **Arrancar con un buen gap:** idealmente Nivel 1 (valor de shock, gapeando sobre pivotes, hacia un vacío, sin ser excesivo), con RS/RW y preferentemente volumen de pre-market alto.
2. **Buen gráfico de pre-market:** consolidación limpia — Buy Set-Up, 3 Bar Play o parabólico.
3. **Vigilar el Level II** (en pre-market y en la apertura): preferentemente con volumen grande en el precio de entrada buscado, prestando atención al balance de poder y a spreads/whippiness.
4. **Entrar al precio predeterminado** y gestionar la posición según el plan ya definido.

### Ejemplos de trades reales con resultado (P&L)
El capítulo cierra con una serie de casos reales de Live Traders que ilustran el proceso completo funcionando: un MFTA (multiple timeframe alignment) en CF que devolvió 7:1; un 1' HI/ORB con gap de Nivel 1 en LULU que generó $928 en 50 segundos; un 3 Bar Play en WFM con ratio cercano a 8:1 ($4.000 de ganancia sobre $500 de riesgo en menos de una hora); un Buy Set-Up intradía temprano en TSLA con retorno 8:1 en 30 minutos; un breakout de 5' en COMM; un breakout de 1' en VRX con retorno 6:1 en 3 minutos; un Super Curl de 2' en CONN; y un caso de "satisfacción matutina" combinando un trade con edge de pre-market (HPQ) y otro sin esa ventaja pero con paciencia y confirmación (CF, 4 Bar Play de 2'), sumando $2.374 y terminando la operativa del día antes de las 10am.

### Cierre del curso
Los aspectos psicológicos representan el 99% del éxito en el trading: sin poder gestionarse a uno mismo, no hay éxito posible, y nunca hay que subestimar el poder de la objetividad. La clave para controlar esto es la **disciplina**, definida como "la capacidad de seguir el propio plan" — y la clave para obtener disciplina está en construir y usar un plan de trading que se ajuste a la propia personalidad. Reflexión final del curso: tomarse varios días para "recargar" antes de repasar el manual; luego pensar en el trader que se quiere llegar a ser dado el propio perfil de personalidad, tiempo y capital; elegir el estilo y los timeframes más adecuados; construir el plan empezando con 2 patrones básicos y una rutina simple; hacer paper trading varias semanas y recién después operar con **montos pequeños** de dinero real. Mensaje de cierre de Live Traders: son firmes creyentes en que la experiencia real de mercado es el factor más importante para el éxito — "hay que aprender EN los mercados", porque solo así se pueden sentir de verdad las emociones de la rutina diaria.

### Apéndice (material de referencia)
El curso cierra con un apéndice útil como consulta permanente: un **glosario completo de abreviaturas** (todos los acrónimos usados a lo largo del curso: +3BP/-3BP, BS/SS, WRB/NRB, RS/RW, MTFA, AON/BBB/PM, niveles de gap, etc.); una **lista de lecturas recomendadas** (Psycho-Cybernetics de Maxwell Maltz, Trading in the Zone y The Disciplined Trader de Mark Douglas, Trade Your Way to Financial Freedom de Van Tharp, Market Wizards de Jack Schwager, los libros de R. Wyckoff sobre los métodos de Jesse Livermore, entre otros); una sección de **"Keys to Success"** con principios de conciencia personal (conocerse a uno mismo, construir una psicología para el éxito, nunca victimizarse, nunca rendirse) y de conciencia de trading (llevar registro de todos los trades, nunca hacer "revenge trading" —"Elmer Fudd Syndrome"—, no sobre-operar, gestionar el gráfico y no el P&L, aceptar que la mayoría de las ganancias se concentran en 2-3 días por semana); **5 principios de trading** (el money management está por encima de todo; el 75% de las acciones se mueven con el mercado; es raro que una tendencia dure más de 6-8 velas sin corrección — los ciclos suelen ser de 3-6 velas; el primer intento fallido de un nuevo mínimo/máximo en una tendencia establecida es la primera señal de cambio de balance de poder; sin control emocional es casi imposible ganar dinero, de ahí la importancia de operar según la propia personalidad); una plantilla de **reglas generales de trading** en primera persona (compromiso tipo "voy a..."); una **"Lot Size Cheat Sheet"** (tabla de referencia rápida de tamaño de posición según nivel de riesgo en dólares y tamaño del stop); y una planilla de **registro de operaciones (Trade Log Sheet)** lista para usar.

---

## Notas para nuestra estrategia (Bolsa de Valores / sistema propio)

Puntos de la Parte 1 directamente aplicables al sistema que ya tenemos documentado (day/swing trading, ToS, reglas R1-R10):

- Confirma el enfoque ya adoptado: **entry/stop/target obligatorios antes de cualquier orden** (coincide con R2 de nuestro sistema).
- Refuerza la prioridad de **money management y psicología por sobre el patrón técnico en sí** — insumo para no sobre-optimizar el scanner sin antes tener disciplina de riesgo sólida.
- La idea de "elegir 1-2 estrategias y repetir con consistencia" es coherente con tener day trading y swing trading como las únicas dos estrategias activas (scalping descartado).

Puntos de la Parte 2 aplicables/cruzables con nuestro sistema:

- El ciclo de 4 etapas (Wyckoff/Weinstein) es un candidato fuerte para afinar el **paso 2 del árbol de clasificación del scanner** (timeframe del setup): un breakout desde stage 1 (rango angosto, bajo volumen) con vela de rango amplio = catalizador típico de day trade; un stage 2 ya establecido con pullback a la EMA = setup típico de swing.
- La regla de **"esperar el breakout del rango lateral y comprar el primer pullback"** es exactamente el tipo de setup de "ruptura de rango" que ya tenemos en la sección de gestión de target — se puede usar como filtro de entrada, no solo de salida.
- HPH/HPL y LPH/LPL (estructura de pivotes) dan un criterio objetivo y verificable para el criterio #5 de nuestro árbol de decisión (posición vs. SMA 200): confirmar que el swing esté a favor de la tendencia mayor viendo si los pivotes son crecientes o decrecientes, no solo la posición relativa a la media.
- El enfoque "Intra-day Swing Trading" (vender parte EOD, dejar correr el resto) es una variante interesante para el criterio #7 de capital disponible: permite liberar parte del capital el mismo día sin resignar el upside de un swing, algo a evaluar dado el capital acotado.
Puntos de la Parte 3 aplicables/cruzables con nuestro sistema:

- El **checklist de 8 criterios para breakouts/breakdowns** (base prolija, cercanía a la EMA, volumen decreciente en la base + spike en la entrada, HOD/LOD, número redondo, void arriba/abajo) es directamente formalizable como filtro adicional del scanner, más allá de RelVol/ATR% — da un chequeo objetivo de "calidad" de la ruptura antes de operarla.
- El **Buy/Sell Set-Up** (pullback secuencial con <50% de overlap y ángulo ~45°) aporta una definición geométrica precisa de lo que hoy en nuestro sistema describimos de forma más laxa como "pullback a media móvil" — se puede usar como criterio de entrada objetivo tanto en day trade (setup de pullback) como en swing.
- El **3/4 Bar Play** da una definición mecánica y muy replicable para el "setup de catalizador intradiario fuerte" que ya tenemos en la gestión de target — útil para programar una alerta o regla de scanner concreta en vez de depender solo del criterio visual.
- La combinación **vela de giro (turnaround) + 3 Bar Play**, señalada como especialmente potente, es candidata a un "tier" de señal de mayor confianza dentro del árbol de clasificación (más peso que un setup aislado).
- El **Parabolic Buy/Sell Set-Up** encaja con la idea de operar reversiones extremas, pero el propio material advierte que su R:R típico (~2:1) está en el piso de nuestra regla R3 (mínimo 1:2 universal) y que requiere psicología y ejecución avanzada (alta probabilidad de necesitar 2 entradas) — con capital acotado conviene priorizarlo solo cuando haya experiencia y margen para el reintento, no como setup por defecto.
Puntos de la Parte 4 aplicables/cruzables con nuestro sistema:

- El concepto de **"pattern booster"** (puntuar cada setup por cuántos atributos de calidad confluyen: BT/TT, NRB/NBB, COC, tipo de volumen, nivel de soporte, % de retroceso, RS/RW, cercanía a EMA, MTFA, Market Timing) es directamente trasladable como **motor de scoring del scanner** — en vez de un filtro binario (pasa/no pasa), cada acción candidata podría puntuarse por cantidad de boosters presentes, priorizando las de mayor puntaje del día.
- Las definiciones cuantificadas de **Igniting/Ending/Resting Volume** (2x+ el promedio para iniciar o terminar un movimiento, ~0.5x para sostenerlo) dan un criterio más preciso que nuestro RelVol genérico (1.5x-3x) — se puede diferenciar entre "volumen que confirma entrada" y "volumen que anticipa agotamiento/reversión", algo que hoy no distinguimos explícitamente en el sistema.
- El framework **Bias (TF mayor) vs. Entry (TF menor)** de MTFA coincide con nuestra regla ya adoptada de revisar 2-3 timeframes antes de entrar (ver notas de la Parte 2) — suma un matiz nuevo: la **falla de un patrón en el TF menor puede señalar la entrada correcta en el sentido contrario en el TF mayor**, útil como filtro adicional de confirmación.
- **Market Timing** (5 categorías de mercado, con la regla "nunca ir en contra de un extremo salvo que sea parabólico") es un candidato directo para formalizar como filtro de régimen de mercado usando SPY/QQQ antes de tomar cualquier trade con RS/RW — complementa (no reemplaza) nuestras reglas de no operar durante eventos de alto impacto (FOMC, NFP, CPI).
- La EMA 200 en 60'/diario se destaca como la media más potente de todas ("rara vez se rompe sin reacción") — vale la pena tratarla como nivel de referencia obligatorio en ThinkOrSwim para targets y gestión de swings, más allá de la SMA 200 que ya usamos.
Nota: a partir de acá, estas comparaciones quedan solo como insumo para una evaluación posterior — todavía no está decidido si se van a usar para mejorar el sistema actual, para armar una estrategia adicional, o si se descartan. Esa decisión la vamos a tomar más adelante, con todo el material ya reunido.

**Parte 5 (Gaps) — puntos a tener en cuenta para esa evaluación futura:**

- El sistema de rating de gaps (Nivel 1/2/3, con matices "+"/"-") reutiliza directamente conceptos ya definidos en la Parte 4: pivotes, soporte/resistencia y volumen de "shock". Es un candidato a evaluar como filtro de scanner independiente, o como base de una estrategia de gaps separada del day/swing actual.
- El detalle de que el % de gap por sí solo no define "excesivo" (depende del precio de la acción) es un matiz concreto que valdría la pena contrastar con nuestro filtro actual de "variación diaria > ±2%", que hoy no distingue por precio.
- La escala de agresividad de entrada según nivel de gap (inmediata en Nivel 1 vs. esperar hasta 9:45am en Nivel 3) es un enfoque de gestión de entrada distinto al que usamos hoy, a comparar más adelante.
- Falta ver los capítulos de Super Plays (Cap. 6) y Order Entry (Cap. 7) antes de tener el panorama completo para decidir si los gaps ameritan una estrategia propia o quedan como complemento.

**Parte 6 (Super Plays) — puntos a tener en cuenta para esa evaluación futura:**

- El concepto de "Super Play" (combinar 2 patrones esenciales en el mismo punto) es una extensión directa del scoring por "pattern boosters" de la Parte 4 — mismo mecanismo, aplicado a nivel patrón en vez de nivel atributo individual.
- La gestión del Super Curl (target parcial en HOD, trailing con EMA 9, o salida 2-3R) es un esquema de salida concreto y distinto al que usamos hoy (parcial en 1R + trailing), a comparar más adelante.
- El caso "Perfección" (gap Nivel 1 + Super Play) sugiere que el mayor valor no está en cada elemento aislado sino en la combinación — coherente con la lógica de scoring ya registrada en la Parte 4.

**Parte 7 (Order Entry) — puntos a tener en cuenta para esa evaluación futura:**

- La regla de tamaño de stop-limit (stop loss ÷ 5 + un par de centavos, siempre errando hacia lo más ancho) es un cálculo concreto y fácil de aplicar en ThinkOrSwim, distinto a cómo definimos hoy el ancho de entrada.
- El concepto de "Anticipation Stop Out" es una advertencia específica sobre el riesgo de anticipar entradas — relevante si en algún momento se evalúa adelantar órdenes en day trading.
- La distinción entre agregar y remover liquidez (créditos/débitos ECN) es un tema a verificar con la estructura de comisiones real de Schwab/ToS antes de asumir que aplica igual — muchos brokers minoristas ya no cobran comisión por acción y el esquema de rebates puede no ser visible o relevante de la misma forma.
- El resto del capítulo (tipos de orden, lectura de Level II) es más una base operativa que una estrategia en sí — más relevante para la ejecución que para la decisión de qué operar.

**Parte 8 (Money & Trade Management) — puntos a tener en cuenta para esa evaluación futura:**

- El sistema de límites acumulados en capas (2R de exposición simultánea máxima, 3R de pérdida diaria, 9R semanal, 12R mensual con reducción a medio lote) es un esquema más granular que nuestro R4 actual (3% diario) — candidato a comparar en términos de rigor y practicidad.
- La regla de "ganarse el derecho a subir el riesgo" basada en resultados, no en necesidad, es un principio de disciplina a contrastar con cómo se define hoy el escalado de riesgo en el sistema.
- Los 7 estilos de gestión de trade (AON, BBB, Pivot, EMA, Add & Reduce, Sell Into Strength, Combination/Hybrid) son un catálogo completo y explícito de opciones de trailing/salida — hoy el sistema usa una versión simplificada (parcial en 1R + trailing por debajo de mínimos), y este catálogo da alternativas concretas para evaluar caso por caso.
- La estadística de "re-entrada tras stop-out completo" (84% de efectividad según la experiencia del autor) es una hipótesis puntual, no una regla validada — el propio material pide backtestearla antes de usarla; interesante como candidata a probar con datos propios más adelante.
- La gestión de metas de ganancia (parar al llegar a la meta, o seguir con reglas específicas) es un componente que hoy no está explícitamente definido en el sistema — el enfoque actual define bien el límite de pérdida pero no un protocolo simétrico para las ganancias del día.

**Parte 9 (The Business of Trading & Psychology) — puntos a tener en cuenta para esa evaluación futura:**

- El checklist de entrada con **7 "must haves" + 3 "like to haves"** es una forma concreta de convertir el scoring por "pattern boosters" (Parte 4) en un filtro de aprobación/rechazo con umbral numérico — candidato a probar como regla dura del scanner en vez de un chequeo cualitativo.
- El timeline realista de **12-36 meses** para volverse rentable y el desglose de costos del primer año son un benchmark de planificación a contrastar con las expectativas y el horizonte de tiempo que se manejan hoy para el desarrollo del sistema propio.
- La estructura completa de **plan de trading escrito** (misión, metas, money management, checklist de entrada, rutina pre-mercado/intradía/cierre) es un molde de documento a comparar con la organización actual del sistema (hoy repartido en reglas R1-R10, árbol de clasificación y flujo diario) — posible candidato a reorganizar como documento único si se decide en la evaluación.
- El combo **diario de trading + planilla de tracking** (uno capta el sesgo psicológico, el otro los números reales) es un sistema de journaling más detallado que lo que hoy se registra — a evaluar como capa adicional de "Diario de Trading" ya prevista en el sistema propio.
- El ejemplo de backtesting comparando 8 métodos de gestión sobre 80 trades (rango de 19.34R a 44.31R solo cambiando el estilo de salida) refuerza la utilidad del backtesting de parámetros ya identificado como próximo paso del roadmap del sistema propio — es evidencia concreta de cuánto puede variar el resultado por gestión, sin tocar el criterio de entrada.
- El framework de **share sizing por estilo** (Core 1.5%, Swing 1.0%, Intra-day 0.5%) y la regla de "BP ÷ 1.000" para day traders son puntos de referencia cuantitativos a comparar con el R1 actual (1-2%, arrancando en 1%).
- La comparación Retail vs. Prop (capital mínimo, apalancamiento, retorno esperado, posibilidad de overnight) es relevante si en algún momento se evalúa migrar o complementar la cuenta actual de Schwab con una cuenta prop.
- El framework de **"definirse a uno mismo"** (personalidad, tiempo disponible, capital, intangibles) para elegir el estilo de gestión es un ejercicio de autodiagnóstico que podría aplicarse directamente para decidir, en la evaluación futura, si conviene mantener el sistema actual, ajustarlo, o construir una estrategia alternativa mejor alineada con el perfil real del trader.
- El principio de que el 95% del trading es psicológico y de que la "auto-gestión" es la base de money management y trade management es un recordatorio a tener presente durante toda la evaluación: cualquier comparación de reglas técnicas entre sistemas es secundaria si no hay antes disciplina para seguirlas.

**Parte 10 (Pre-Market & Early Charts) — puntos a tener en cuenta para esa evaluación futura:**

- La regla "movimiento extendido en pre-market = esperar, movimiento no extendido = entrar de inmediato" es un criterio concreto y simple para el pre-mercado (8:30-9:25am ET) que hoy no está formalizado en el flujo de trabajo diario del sistema propio — hoy se marcan niveles clave pero no se define explícitamente esta regla de extensión.
- El énfasis en operar solo sobre la watchlist de favoritos ya preparada ("Focus on Favs") refuerza el valor de tener la lista clasificada por nivel de gap antes de la apertura, algo que el sistema propio ya contempla en el scanner Finviz — este capítulo lo confirma como crítico, no solo como buena práctica.
- La reiteración de "Excessive Gap = Fade/Stay Away" es consistente con la nota ya registrada en la Parte 5 sobre el filtro de variación diaria — otro punto de encuentro entre capítulos que refuerza esa evaluación pendiente sobre el criterio de "gap excesivo" según el precio de la acción.
- El criterio de "cuándo esperar" (sin edge, gap Nivel 3, iliquidez, spread excesivo, patrón que no dispara) es un checklist corto y aplicable tal cual como filtro de decisión rápida en los primeros minutos de la sesión, complementario al árbol de clasificación día/swing ya existente.
- La ventana de tiempo tan acotada que muestran los ejemplos (trades resueltos en minutos, o sin entradas posibles después de las 9:31am) es un dato relevante para dimensionar cuánta preparación previa (niveles, favoritos, stops ya calculados) hace falta antes de la apertura si se quisiera operar con este enfoque.

**Parte 11 (Putting It All Together + Apéndice) — puntos a tener en cuenta para esa evaluación futura:**

- Los "5 escenarios de sesgo de mercado según el gap" son un framework más granular que la categoría genérica de "Market Timing" de la Parte 4 — específico para la apertura, y candidato a formalizarse como paso explícito de la rutina de pre-mercado.
- El checklist completo de rutina matutina (sesgo de mercado, escaneo de gaps por múltiples fuentes, clasificación por nivel, favoritos en gráficos miniatura priorizados, chequeo de noticias, "operar solo lo que está en la watchlist") es prácticamente un molde de proceso operativo — se puede comparar punto por punto con la rutina pre-mercado ya definida en el sistema propio (Parte 9) para ver qué falta.
- El proceso resumido en 4 pasos ("buen gap → buen gráfico de pre-market → vigilar Level II → entrar al precio predeterminado") condensa en una secuencia simple todo lo visto en las Partes 5, 6, 7 y 10 — útil como checklist final de decisión antes de cada entrada de apertura, más allá de si se adopta la estrategia completa.
- Los "5 principios de trading" del apéndice (money management por encima de todo, 75% de las acciones siguen al mercado, rareza de tendencias de más de 6-8 velas sin corrección, la primera falla de un nuevo mínimo/máximo como señal de cambio de tendencia, la necesidad de operar según la propia personalidad) son afirmaciones generales y verificables — buenos candidatos a contrastar empíricamente en el backtesting ya previsto en el roadmap del sistema propio.
- El glosario de abreviaturas y la "Lot Size Cheat Sheet" del apéndice son herramientas de referencia rápida que podrían adaptarse directamente (traducidas y con los parámetros de riesgo propios) como material de consulta para operar, independientemente de qué se decida sobre el resto del contenido del curso.
- La reflexión de cierre sobre expectativas de tiempo (paper trading varias semanas, empezar con montos pequeños, aprender "en los mercados") refuerza —por tercera vez en el curso— el mismo mensaje ya registrado en la Parte 9 sobre plazos realistas: es un punto que aparece con tanta insistencia en el material que amerita peso especial en la evaluación final.

---

**Nota de cierre:** con esta Parte 11 se completó el resumen de los 13 capítulos del curso "Professional Trading Strategies" de Live Traders. El documento queda disponible como fuente de consulta completa. La evaluación pendiente (qué tomar para mejorar el sistema actual, qué usar para armar una estrategia adicional, y qué descartar) queda para una etapa posterior, a decidir con todo el material ya reunido.
