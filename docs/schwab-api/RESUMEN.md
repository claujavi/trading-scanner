# Resumen — PDFs oficiales de Schwab Developer Portal

Fuente: "Trader API - Individual" (Market Data Production + Accounts and Trading Production),
descargados 2026-07-16. Resumen para no tener que releer los PDFs completos cada vez.

## OAuth / tokens

- Access token: **30 minutos**.
- Refresh token: **7 días**. Esto SÍ está documentado oficialmente por Schwab (contradice lo que
  decía CLAUDE.md sobre que era solo una inferencia empírica — corregido).
- Vencido el refresh token, hay que rehacer el flujo completo (CAG/LMS vía `/schwab/connect`), no
  hay forma de renovarlo sin intervención del usuario.

## Rate limits / throttling

- **Solo documentado para endpoints de órdenes** (POST/PUT/DELETE en `/trader/v1/.../orders`):
  configurable de 0 a 120 requests/minuto por cuenta según la app. Los GET de órdenes no tienen límite.
- **No hay ninguna mención de rate limit para `/marketdata/v1/pricehistory`** (el endpoint que usa
  `schwab_history.py`) ni para quotes en general.
- Conclusión práctica: el `403 Access Denied` de `errors.edgesuite.net` (Akamai) que tumbó el
  backtest del 2026-07-16 no es un rate-limit documentado de la API — es protección de borde (WAF)
  no publicada, que reacciona a ráfagas de requests concurrentes. No hay un número oficial de
  Schwab al que apuntar; el semáforo de concurrencia en `runner.py` es la mitigación correcta,
  ajustada por prueba y error.

## Streamer API (WebSocket) — referencia para cuando se implemente `schwab_stream.py` (Sprint 2)

- **Una sola conexión de Streamer por usuario a la vez** (excederla da código `12 CLOSE_CONNECTION`).
  Confirma que la arquitectura ya prevista en CLAUDE.md (una conexión persistente para todos los
  tickers suscritos, no una por ticker) es la correcta.
- Login: primer mensaje debe ser `service: ADMIN, command: LOGIN` con el access token (`Authorization`
  header no aplica acá, va en el body del mensaje JSON). Debe tener éxito antes de mandar cualquier
  otro comando — si no, error `20 STREAM_CONN_NOT_FOUND` (race condition típica: mandar SUBS antes de
  que LOGIN confirme).
- Comandos: `LOGIN`, `SUBS` (reemplaza toda la suscripción del servicio), `ADD` (agrega sin pisar lo
  existente — el que conviene usar para tickers nuevos durante sesión), `UNSUBS`, `VIEW`, `LOGOUT`.
- Servicios relevantes para este proyecto:
  - `LEVELONE_EQUITIES`: quotes en tiempo real (bid/ask/last/volumen), delivery tipo "Change" (solo
    manda campos que cambiaron, conflateado).
  - `CHART_EQUITY`: velas de 1 minuto en tiempo real, delivery "All Sequence" (todo, con número de
    secuencia, sin conflate).
- Heartbeats vía mensajes `notify`. Reconexión: hay que rehacer LOGIN + re-suscribir todo — no hay
  resume de sesión.
- `STOP_STREAMING` (código 30): el server puede cerrar la conexión por inactividad o lentitud del
  cliente — hay que manejar reconexión con backoff, como ya prevé CLAUDE.md.

## Órdenes (Sprint 5, futuro lejano — no aplica todavía)

- Símbolos de opciones: `RRRRRR` (6 chars, root con espacios de relleno) + `YYMMDD` + `C`/`P` +
  strike (5 enteros + 3 decimales, sin punto). Ej: `AAPL  251219C00200000`.
- Tipos de orden soportados con ejemplos completos en el PDF: market, limit, vertical spread
  (NET_DEBIT), trigger (OCO), one-cancels-other, trailing stop. Útil como referencia de payload
  cuando se implemente ejecución real.
