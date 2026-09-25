# Alternativa: distribución en el edge (Cloudflare) y otros hostings

> **Qué es este documento:** una alternativa **no implementada** para el fan-out a audiencias grandes, más la comparación de hostings. Lo implementado está en [`ARCHITECTURE.md` §2](../ARCHITECTURE.md#2-arquitectura-actual-implementado). La capacidad observada, en [`CONCURRENCY-REPORT.md`](../CONCURRENCY-REPORT.md). Estados según [su convención](../CONCURRENCY-REPORT.md#convención-de-estados). Ninguna cifra de este documento es una **capacidad garantizada**: son límites del proveedor (DOCUMENTED, con fecha) o cuentas (HYPOTHESIS) hechas con tasas medidas.
>
> Última revisión: 2026-09-25 (antes: `alternativas-sesiones/OPCIONES-ESCALADO.md`). Las alternativas de motor (Gemini con billing, motor por sala, navegador, modelos abiertos) pasaron a [`TRANSCRIPTION-ENGINES.md`](TRANSCRIPTION-ENGINES.md).

## TL;DR

1. **El hosting no cambia el cupo de Gemini.** HF, Cloudflare u Oracle abren la misma cantidad de sesiones Live: el límite es por proyecto de Google.
2. **Durable Objects (DO) resuelve coordinación, estado y fan-out distribuido. No resuelve la concurrencia de Gemini.** Encaja como capa de audiencia: el motor sigue en Python y publica los subtítulos a un DO por sala.
3. Hoy no hace falta: el fan-out actual se mide con `audience_load` ([reporte §7](../CONCURRENCY-REPORT.md#7-prueba-de-audiencia-sin-gemini)). DO queda como **opción futura** ([`ARCHITECTURE.md`](../ARCHITECTURE.md#decisiones-vigentes) D11).

## 1. Hostings comparados

| Opción | Qué corre dónde | Oyentes | Límites del plan gratis | Estado |
|---|---|---|---|---|
| **B1.** Solo HF Space (actual) | Todo en un container Python | Ver reporte §7 (medido en local; en el Space, `EXPERIMENT`) | 2 vCPU / 16 GB; límites de red sin verificar | En uso |
| **B2.** HF (motor) + Cloudflare DO (audiencia) | Motor en HF; un DO por sala hace el fan-out | Sin cifra publicada de WebSockets por DO (ver §2) | Ver §2 | Opción futura |
| **B3.** Todo en Cloudflare (motor dentro de un DO) | Motor portado a TS | Igual que B2 | Igual que B2, más la conexión a Gemini **sin hibernar** | **Descartada** ([decisiones descartadas](../ARCHITECTURE.md#decisiones-descartadas-y-por-qué)) |
| **B4.** Oracle Cloud Always Free | Todo en una VM ARM | Más CPU que HF | Vigencia sin verificar | Alternativa, operación manual |
| **B5.** Google Cloud Run | Container con autoscaling | — | Exige billing; estado en memoria → sticky sessions | Descartada |
| **B6.** Render / Fly.io free | Container | Bajo | Sin verificar | Descartada |

## 2. Límites de Cloudflare relevantes (DOCUMENTED, consultados el 2026-09-25)

| Dimensión | Plan Free | Fuente |
|---|---|---|
| Requests a DO | 100.000 / día (reset 00:00 UTC) | [DO pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/) |
| Duración | 13.000 GB-s / día | DO pricing |
| Mensajes WebSocket | Entrantes: 20 mensajes = 1 request. **Salientes: sin cargo** | DO pricing |
| Hibernación | Los objetos elegibles para hibernar no generan cargo de duración | DO pricing |
| Al superar un límite | "las operaciones de ese tipo fallan con error" (no cobra) | DO pricing |
| Storage (SQLite) | 5 M filas leídas/día · **100.000 filas escritas/día** · 5 GB en total | DO pricing |
| CPU por request (DO) | 30 s (default) | [DO limits](https://developers.cloudflare.com/durable-objects/platform/limits/) |
| CPU por request (Worker, sin DO) | 10 ms | [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) |
| Memoria | 128 MB por isolate (Workers) | Workers limits |
| Requests por segundo por objeto | Límite blando de 1.000 | DO limits |
| WebSockets por DO | **No publicado** en las páginas consultadas (la cifra de 32.768 que citaba la versión anterior no aparece) | DO limits, [WebSockets](https://developers.cloudflare.com/durable-objects/best-practices/websockets/) |
| Hibernación y memoria | Al hibernar se pierde el estado en memoria; `serializeAttachment` guarda hasta 16 KB por conexión | WebSockets |
| Conexiones salientes | "**Outgoing WebSockets do not hibernate**" (mantienen vivo el objeto) | WebSockets |

## 3. Cuentas para B2 (HYPOTHESIS, con tasas medidas)

<!-- CUENTAS -->

## 4. Cómo quedaría B2 (si se hace)

```
PLANO DE CONTROL Y MOTOR (HF Space, Python — sin cambios)        PLANO DE AUDIENCIA (Cloudflare)

Mini PC ──audio WS──► FastAPI ──WSS──► Gemini Live
                        │
                        │ CaptionEvent (1 WS por sala, con token)
                        └──────────────────────────────► Worker ──► DO "sala-1" ──► celulares / OBS
                                                                 ├─► DO "sala-2" ──► ...
Consola y vista de escenario → HF                        Página de audiencia (estática) → Cloudflare
```

Esfuerzo estimado (HYPOTHESIS): Worker + DO de ~150 líneas en TS, un `CloudflarePublisher` de ~60 líneas en Python, URL de WS configurable con fallback a HF en la página de audiencia, y un test de carga.

## 5. Por qué no B3 (todo en Cloudflare)

- La conexión a Gemini sería un WebSocket **saliente**, y esos **no hibernan**: la duración se cobra toda la charla (DOCUMENTED).
- Hay que portar a TS código que ya anda y tiene tests.
- **No agrega ni una sesión Live.**
- Que `google-genai` funcione en Python Workers: sin verificar.

## Fuentes (consultadas el 2026-09-25)

- Cloudflare DO pricing: https://developers.cloudflare.com/durable-objects/platform/pricing/
- Cloudflare DO limits: https://developers.cloudflare.com/durable-objects/platform/limits/
- Cloudflare DO WebSockets: https://developers.cloudflare.com/durable-objects/best-practices/websockets/
- Cloudflare Workers limits: https://developers.cloudflare.com/workers/platform/limits/
- Gemini API rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Google APIs Terms (API Limitations): https://developers.google.com/terms
