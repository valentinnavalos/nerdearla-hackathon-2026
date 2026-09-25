# Roadmap y tareas — Nerdearla Live Captions

> **Qué es este documento:** qué se hace, en qué orden y en qué estado está. Tiene el tablero, el roadmap de escalabilidad, el backlog completo, la entrega y los riesgos. El *cómo está hecho* y el *por qué* están en [`ARCHITECTURE.md`](ARCHITECTURE.md). Las cifras de capacidad, en [`CONCURRENCY-REPORT.md`](CONCURRENCY-REPORT.md).
>
> Última revisión: 2026-09-25.

## Índice

1. [Convenciones](#1-convenciones)
2. [Estado actual](#2-estado-actual)
3. [Tablero](#3-tablero)
4. [Roadmap de escalabilidad](#4-roadmap-de-escalabilidad)
5. [Tareas](#5-tareas)
6. [Entrega](#6-entrega)
7. [Riesgos y plan B](#7-riesgos-y-plan-b)

---

## 1. Convenciones

### Restricciones de equipo y tiempo

| Tema | Decisión |
|---|---|
| Equipo | 2 personas: **A** = motor / backend Python, **B** = web / deploy |
| Tiempo | 15 h de reloj en paralelo. El MVP cierra en H8 |
| Deadline | Devpost antes del **25/9 15:00 UTC** (12:00 ART), con 1 h de margen |
| Audio de prueba | 2 archivos mp3 propios (`samples/`) |

Las restricciones de producto (costo cero, idiomas, hosting, frontend) están en [`ARCHITECTURE.md`](ARCHITECTURE.md#restricciones-de-producto-y-técnicas).

### Leyenda

- **Dueños:** **A** = motor / backend Python · **B** = web / deploy · **AB** = ambos.
- **Prioridad:** **P0** = MVP intocable · **P1** = importante para el jurado · **P2** = stretch (se recorta primero).
- **Tiempos:** relativos al arranque (H0). Checkpoints de sincronización: **H3.5**, **H8**, **H12.5**.
- **Estado:** ✅ completo · 🟡 hecho, falta validar (ver la nota de la tarea) · ⛔ bloqueado · ➖ no aplica · (vacío) pendiente.

### Convenciones de trabajo

- `main` siempre deployable. Commits chicos y frecuentes; cada uno debe dejar el Space funcionando.
- Deploy manual: `make deploy HF_SPACE=<usuario>/<space>` (sube el árbol con `hf upload`). Cada checkpoint se valida **en el Space**, no en local.
- Nunca commitear `.env` ni keys. Nunca loguear la API key.
- Toda variable nueva se agrega a `.env.example` y a la tabla de variables del README en el mismo commit.
- Si una tarea supera su estimación en más de 50%, avisar al otro y decidir: seguir, simplificar o recortar.

---

## 2. Estado actual

- **Fase:** 2 (Core). Fase 0 completa; Fase 1 completa salvo validar en el Space (T1.12, T1.13, T1.14 🟡).
- **Funciona:** motor Camino 1, sesiones con pub/sub por idioma, WS de subtítulos, página de audiencia, replay, `CapacityGuard` (409), `CaptionWriter` asíncrono, `LoopLagMonitor`, Dockerfile y probes de concurrencia.
- **Bloqueos:**
  - **T2.1** (rotación): sin ella una sala no pasa de ~10 min y no se puede hacer la prueba sostenida (T2.10c/d).
  - **T2.12** (medición del probe): el barrido del 25/9 tiene defectos de medición que impiden cerrar el veredicto de concurrencia ([reporte §6](CONCURRENCY-REPORT.md#validez-de-la-medición)).
- **Próximo:** T1.13 deploy al Space → T2.5 API admin → T2.1 rotación → T2.18 arranque escalonado → T2.10c. En paralelo: T2.12 → T2.13. El resto de "Escalado y resiliencia" (T2.14–T2.21) va después de cerrar los P0 de Fase 2.

---

## 3. Tablero

| ID | Tarea | Dueño | Est. | Prio | Fase | Estado |
|---|---|---|---|---|---|---|
| T0.1 | Proyecto y API key sin billing | AB | 15 min | P0 | 0 | ✅ |
| T0.2 | Relevar cuotas + prueba cualitativa en AI Studio | A | 20 min | P0 | 0 | ✅ |
| T0.3 | Decidir Camino 1 o 2 | AB | 5 min | P0 | 0 | ✅ |
| T0.4 | Estructura del repo, `.env.example`, Makefile | B | 20 min | P0 | 0 | ✅ |
| T0.5 | Congelar contratos (evento, Engine, endpoints) | AB | 20 min | P0 | 0 | ✅ |
| T1.1 | Fix `FileSource`: productor/consumidor, pacing, loop | A | 25 min | P0 | 1 | ✅ |
| T1.2 | Actualizar `google-genai` y verificar features | A | 10 min | P0 | 1 | ✅ |
| T1.3 | `LiveSessionRunner` v0 + CLI | A | 45 min | P0 | 1 | ✅ |
| T1.4 | Spike de mediciones | A | 30 min | P0 | 1 | ✅ |
| T1.5 | Engine del camino elegido | A | 45 min | P0 | 1 | ✅ |
| T1.6 | Traductor local Argos (solo Camino 2) | A | 30 min | P0* | 1 | ➖ |
| T1.7 | Módulo de glosario | A | 20 min | P0 | 1 | ✅ |
| T1.8 | Esqueleto FastAPI + config | B | 20 min | P0 | 1 | ✅ |
| T1.9 | `SessionManager` + `Session` + pub/sub | B | 40 min | P0 | 1 | ✅ |
| T1.10 | `ReplayEngine` + jsonl de ejemplo | B | 20 min | P0 | 1 | ✅ |
| T1.11 | WS de captions | B | 20 min | P0 | 1 | ✅ |
| T1.12 | Página de audiencia v0 | B | 40 min | P0 | 1 | 🟡 |
| T1.13 | Dockerfile HF + primer deploy | B | 40 min | P0 | 1 | 🟡 |
| T1.14 | Integración checkpoint H3.5 | AB | 15 min | P0 | 1 | 🟡 |
| T2.1 | Rotación + resiliencia del runner | A | 1.5 h | P0 | 2 | |
| T2.2 | Aislamiento multi-sala | A | 25 min | P0 | 2 | |
| T2.3 | Persistencia (`captions.jsonl`, `meta.json`) | A | 20 min | P0 | 2 | 🟡 |
| T2.4 | Métricas: nivel, silencio, latencia, cuota | A | 50 min | P1 | 2 | |
| T2.5 | API de administración + auth | A | 35 min | P0 | 2 | |
| T2.6 | WS de ingesta de audio (backend del mic) | B | 25 min | P0 | 2 | |
| T2.7 | Captura de mic con AudioWorklet | B | 1.3 h | P0 | 2 | |
| T2.8 | Vista de escenario (captura + subtítulos + QR) | B | 50 min | P0 | 2 | |
| T2.9 | Consola de operador | B | 50 min | P0 | 2 | |
| T2.10a | 2 sesiones Live aisladas (probe) | A | 15 min | P0 | 2 | ✅ |
| T2.10b | 2 salas con el backend completo, 2–3 min | AB | 15 min | P0 | 2 | |
| T2.10c | 2 salas × 20 min en el Space | AB | 30 min | P0 | 2 | |
| T2.10d | Rotación/reanudación con 2 salas | A | 20 min | P0 | 2 | |
| T2.11 | Video de emergencia | AB | 30 min | P0 | 2 | |
| T2.12 | Corregir la medición de `runner_probe` / `probe_metrics` | A | 40 min | P1 | 2 | |
| T2.13 | Completar el barrido y cerrar el veredicto de concurrencia | A | 1.5 h (reloj) | P1 | 2 | |
| T2.14 | Motor por sala | A | 45 min | P1 | 2 | |
| T2.15 | `/ws/publish` + `ExternalEngine` | A | 40 min | P1 | 2 | |
| T2.16 | `stage.html` modo browser | B | 1.2 h | P1 | 2 | |
| T2.17 | Degradación a browser (un clic, nunca automática) | AB | 30 min | P1 | 2 | |
| T2.18 | Arranque escalonado de sesiones Live | A | 30 min | P0 | 2 | |
| T2.19 | Fan-out eficiente | A | 40 min | P1 | 2 | |
| T2.20 | Test E: 10 salas × 100 clientes | AB | 30 min | P1 | 2 | |
| T2.21 | Render incremental en la audiencia | B | 40 min | P1 | 2 | |
| T3.1 | Modo overlay para OBS/vMix | B | 35 min | P1 | 3 | |
| T3.2 | Panel de monitoreo | B | 1 h | P1 | 3 | |
| T3.3 | Exports SRT / VTT / TXT / MD | A | 45 min | P1 | 3 | |
| T3.4 | Knowledge Pack (generación) | A | 50 min | P1 | 3 | |
| T3.5 | Página de la charla (post-talk) | B | 1.2 h | P1 | 3 | |
| T3.6 | "Preguntale a la charla" | A | 30 min | P1 | 3 | |
| T3.7 | Pasada final de calidad con glosario | A | 30 min | P2 | 3 | |
| T3.8 | Audio traducido (solo Camino 1) | A | 1.5 h | P2 | 3 | |
| T3.9 | Exporter automático a NotebookLM | A | 1.5 h (timebox) | P2 | 3 | |
| T3.10 | `docker-compose.yml` + túnel opcional | A | 20 min | P1 | 3 | |
| T3.11 | Samples, glosario default, replay real | AB | 20 min | P0 | 3 | |
| T3.12 | README completo | B | 1 h | P0 | 3 | |
| T3.13 | Audiencia en Durable Objects | A | 3 h | P2 | 3 | |
| T4.1 | E2E desde cero (otra conferencia) | AB | 30 min | P0 | 4 | |
| T4.2 | Hardening y caminos de error | AB | 25 min | P0 | 4 | |
| T4.3 | Code freeze + tag | AB | 5 min | P0 | 4 | |
| T4.4 | Video final con subtítulos propios | AB | 1 h | P0 | 4 | |
| T4.5 | Envío a Devpost | AB | 30 min | P0 | 4 | |

\* T1.6 era P0 solo con el Camino 2; se eligió el Camino 1.

**Camino crítico:** T0.1 → T0.5 → T1.3 → T1.5 → T1.14 → T2.10a → T2.1 → T2.18 → T2.10c → T4.1 → T4.4 → T4.5.
Todo lo de B corre en paralelo gracias a `ReplayEngine` (T1.10), que simula el motor.

---

## 4. Roadmap de escalabilidad

El modelo (dos problemas distintos, Durable Objects, niveles de capacidad) está en [`ARCHITECTURE.md` §6](ARCHITECTURE.md#6-escalabilidad).

### Objetivos, con su estado

| Objetivo | Estado | Nota |
|---|---|---|
| 2 salas Live concurrentes estables | Ver [reporte §8](CONCURRENCY-REPORT.md#8-veredicto) | Frase canónica: *"2 sesiones concurrentes: capacidad operativa observada, todavía no garantizada"*, hasta que el gate de concurrencia dé PASS y el de ciclo de vida deje de estar bloqueado |
| 3+ salas Live | HYPOTHESIS, con evidencia en contra | En el bloque A3 del barrido, con 3 sesiones ninguna conectó en 2 de 3 trials (reporte §6). Se escala de a una sala y cada paso se justifica con un RESULT |
| **10 salas a $0** | HYPOTHESIS, **no es un objetivo técnico confirmado** | Camino en [`ARCHITECTURE.md` §6.5](ARCHITECTURE.md#65-camino-a-10-salas): salas Live hasta el tope + el resto con motor browser (T2.14–T2.17), arranque escalonado (T2.18). Nunca una key por sala. Se valida con el test E (T2.20) |
| 10 salas Live con billing | HYPOTHESIS | Costo y cupo del Tier 1 a verificar. Capacidad **económica** sin modelar |
| Cientos de oyentes por sala | Ver [reporte §7](CONCURRENCY-REPORT.md#7-prueba-de-audiencia-sin-gemini) | El replay mide el fan-out por separado. Test E (T2.20); si no alcanza, T2.19 y Durable Objects (T3.13) |

### Orden de trabajo

| # | Paso | Estado |
|---|---|---|
| 1 | Runner probe con trials, stagger, capas y clasificación | Hecho (`scripts/runner_probe.py`), con defectos de medición → T2.12 |
| 2 | Instrumentación del event loop | Hecho (`LoopLagMonitor`, `/healthz`) |
| 3 | Confirmar la capacidad y los errores de Gemini (N=1/2/3, stagger, frío y caliente) | En curso: A1, A2, A3 y A4-s5 corridos el 25/9 ([reporte §6](CONCURRENCY-REPORT.md#6-barrido-2026-09-25)); faltan T2.12 y T2.13 |
| 4 | Guardia de capacidad explícita | Hecho (`CapacityGuard`, 409) |
| 5 | `CaptionWriter` asíncrono | Hecho (con tests de disco lento y disco roto) |
| 6 | Arranque escalonado de sesiones Live (`LIVE_START_GAP_S`) | Pendiente (T2.18, P0), antes del paso 7 |
| 7 | Prueba de 2 salas sostenida (20+ min, rotación + reanudación) | **Bloqueada por T2.1** (y T2.18) |
| 8 | Prueba de escalado de audiencia con replay | Pendiente (T2.13, reporte §7) |
| 9 | Motor por sala + motor browser (`/ws/publish`, degradación manual) | Pendiente (T2.14–T2.17) |
| 10 | Optimizaciones de fan-out (JSON una vez por evento, throttle de interims) y render incremental | T2.19 / T2.21; los valores, solo si §7 o el test E muestran que hace falta |
| 11 | Test E: 10 salas × 100 clientes | Pendiente (T2.20) |
| 12 | Durable Objects para el fan-out | T3.13 (P2), solo si el test E muestra límites, o como roadmap de producción |
| 13 | Motores alternativos al browser (Whisper, Parakeet…) | Solo si Gemini + browser no alcanzan para el objetivo de salas |

---

## 5. Tareas

Cada tarea pendiente tiene: qué hace (funcional), cómo se hace (técnico) y cuándo está lista. Las completadas quedan resumidas.

### Fase 0 — Preparación (H0 → H0.75) ✅

| ID | Resultado |
|---|---|
| T0.1 | Proyecto nuevo en AI Studio **sin billing** (tier Free) y API key en el `.env` de ambos |
| T0.2 | Cuotas relevadas en AI Studio y prueba cualitativa de los modelos Live. Google no publica un límite de sesiones Live concurrentes (DOCUMENTED, 2026-09-25): ver [reporte §2](CONCURRENCY-REPORT.md#2-cuatro-capacidades-distintas) |
| T0.3 | **Camino 1** (`ENGINE=live_translate`, `gemini-3.5-live-translate-preview`): decisión D0 en [`ARCHITECTURE.md`](ARCHITECTURE.md#decisiones-vigentes) |
| T0.4 | Estructura del repo (esqueletos incluidos), `.env.example`, `.gitignore`, `Makefile` (`dev`, `test`, `deploy`, `cli`, `docker-*`) |
| T0.5 | Contratos congelados: `CaptionEvent`, `Engine`, `SessionContext` y endpoints ([`ARCHITECTURE.md` §4.4](ARCHITECTURE.md#44-contratos)) |

### Fase 1 — Base y mínimo viable (H0.75 → H3.5)

#### Completadas

| ID | Resultado |
|---|---|
| T1.1 | `FrameQueue` + `pump` en `sources/base.py` (pacing sin deriva, `loop`, descarta el frame más viejo y cuenta `dropped_frames`); `tests/test_file_source.py`. Un mp3 de 3 min con un engine 1,5× más lento que tiempo real tarda 180,2 s |
| T1.2 | `google-genai==2.25.0` (última versión) fijada; campos verificados en `tests/test_genai_features.py` |
| T1.3 | `LiveSessionRunner` v0 (drain de 3 s con tope 30 s, propaga el cierre, hook `on_raw`) + CLI con `engine/factory.py`. `en_talk_3min.mp3`: 36 finales EN, 64 ES, `dropped_frames=0` |
| T1.4 | Las 6 mediciones en [`ARCHITECTURE.md` §3](ARCHITECTURE.md#3-comportamiento-medido-de-gemini-live): fragmentos **delta**, latencia del original ~0,5 s, `GoAway` a los 9:00 y corte a los 9:50 (`1008`), frenazos en EN → ES, reanudación con handle en 1,3 s |
| T1.5 | `core/segmenter.py` (modo delta, `tests/test_segmenter.py`), dos segmentadores en `live_translate.py`, `ChunkedEngine` (fallback A). `SEGMENT_IDLE_S` subió de 1,2 a 2,0 s |
| T1.6 | ➖ No aplica (Camino 1) |
| T1.7 | Glosario: `merge`, `parse_text`, reemplazos con límites de palabra que aceptan `C++`/`Node.js`; `tests/test_glossary.py` (7 casos) |
| T1.8 | `config.py` (`Settings`), `app.py` (lifespan, routers, estáticos), logging `HH:MM:SS LEVEL [sesión] mensaje` |
| T1.9 | `core/session.py` + `core/manager.py`: pub/sub por idioma, historial de 50 finales, colas de 100 por cliente que descartan el más viejo; `tests/test_session.py` |
| T1.10 | `engine/replay.py` (pacing por `t1`, loop con `seg` desplazado) + `samples/replay_demo.jsonl` |
| T1.11 | `/ws/captions/{id}?lang=`: estado + historial + vivo; 4404/4400; `tests/test_ws.py` y cliente WS real contra el contenedor |

#### T1.12 · Página de audiencia v0 — B · 40 min · P0 · depende de T1.11

**Estado:** 🟡 Hecha. Probada en Chromium headless con viewport de celular: lista, interim → final, cambio de idioma sin recargar, A−/A+, alto contraste, reconexión con backoff, sala inexistente. **Falta probarla desde un celular real** (después del deploy).

**Funcional:** cada persona elige sala e idioma y lee subtítulos en su celular.

**Técnico (`index.html` + `js/captions.js`):**
- Sin `?s=`: lista de salas desde `/api/public/sessions` (título, orador, estado, botones de idioma).
- Con `?s=ID&lang=es`: las últimas 2–3 líneas, alineadas abajo; el **interim** en gris itálica se reemplaza cuando llega el **final** del mismo `seg`. Selector de idioma sin recargar. A− / A+ y alto contraste. Reconexión con backoff (1, 2, 4, 8 s, máx. 10 s) e indicador de "reconectando".
- Mobile-first: tipografía grande, sin scroll horizontal.

**Listo cuando:** desde el celular, con `ENGINE=replay`, se ven los subtítulos y se puede cambiar de idioma.

#### T1.13 · Dockerfile HF + primer deploy — B · 40 min · P0

**Estado:** 🟡 Dockerfile listo y probado en local (`make docker-build/test/run`); frontmatter en el README; `make deploy` usa `hf upload`. **Falta crear el Space, cargar los secrets y deployar.**

**Funcional:** que cualquiera pueda deployar con "Duplicate this Space".

**Técnico:**
- `Dockerfile`: `python:3.12-slim` + ffmpeg, usuario no-root UID 1000, `WORKDIR /home/user/app`, `EXPOSE 7860`, uvicorn con `--ws-ping-interval 20 --ws-ping-timeout 20 --proxy-headers --forwarded-allow-ips="*"`.
- Crear el Space (Docker, CPU basic, gratis). Secrets: `GEMINI_API_KEY`, `ADMIN_TOKEN`. Variables: `ENGINE` y, para el checkpoint, `DEMO_FILE=samples/en_talk_3min.mp3`.
- `make deploy HF_SPACE=<usuario>/<space>` (pasos en el README).
- `DATA_DIR=/home/user/app/data` (disco efímero; está bien para la demo).

**Listo cuando:** `https://<usuario>-<space>.hf.space/healthz` responde y la audiencia con replay funciona desde el celular.

#### T1.14 · Integración checkpoint H3.5 — AB · 15 min · P0

**Estado:** 🟡 Validado en local: con `ENGINE=live_translate` y `DEMO_FILE=samples/es_talk_2min.mp3`, dos clientes WS (`?lang=es` y `?lang=en`) recibieron subtítulos solo de su idioma (26 y 24 finales, primer texto a los ~3,5 s, `STOPPED` al final). **Falta repetirlo en el Space desde un celular** (T1.13).

**Listo cuando:** **mp3 → Space → subtítulos en el celular, en los dos idiomas.** Si no se llega, `ENGINE=chunked` y se sigue.

### Fase 2 — Core (H3.5 → H8)

#### T2.1 · Rotación + resiliencia del runner — A · 1.5 h · P0 · depende de T1.4, T2.10a

**Funcional:** una charla de 40 min se subtitula sin cortes visibles aunque Gemini cierre la conexión cada ~10 min.

**Contexto:** ver [`ARCHITECTURE.md` §4.6](ARCHITECTURE.md#46-rotación-de-la-sesión-live-pieza-más-riesgosa-t21). La **conexión** dura ~10 min (`GoAway` a los 9:00 con `time_left=50s`, corte a los 9:50 con `1008`). La **sesión** solo de audio dura 15 min sin compresión y se extiende con `context_window_compression`. El servidor manda `session_resumption_update` (~1/s, `resumable: true`, handle válido 2 h).

**Técnico:**
- **Reanudación como camino principal** (probada en T2.10a: 1,3 s de hueco, sin repetir texto; además evita abrir sesiones nuevas, que es lo que degrada el servicio): conectar con `session_resumption=types.SessionResumptionConfig()` (probar `transparent=True`), guardar el último `new_handle` (`runner.stats["resumption_handle"]` ya lo registra). A los `ROTATE_AFTER_S` (540 s) o al recibir `GoAway`, lo que ocurra primero: cerrar y reconectar con `SessionResumptionConfig(handle=...)`. Estado de la sala: `ROTATING`.
- **Sesiones de más de 15 min:** `context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow())`. Verificar primero que live-translate lo acepta (la doc del modelo no lo menciona).
- **Secuencial:** nunca dos conexiones de la misma sala a la vez (no duplica el cupo).
- **Audio durante la reconexión:** los frames se siguen acumulando y salen apenas conecta. Con `transparent=True`, `last_consumed_client_message_index` indica desde dónde reenviar; sin eso, reenviar solo lo que no se llegó a mandar.
- **Fallback si la reanudación falla** (handle vencido o rechazado): sesión nueva + ring buffer de 2,5 s (`collections.deque`) + **dedupe** (`core/dedupe.py`: `dedupe_overlap(prev_tail, new)`, quita del principio de `new` el prefijo más largo que coincida con las últimas ~15 palabras, normalizando mayúsculas y puntuación; con tests).
- **Errores:** ante excepción de red o 429, reintentar con backoff exponencial + jitter (1, 2, 4, 8, 16, máximo 30 s). Estado `RECONNECTING`. Después de 10 fallos seguidos: `ERROR` (visible en el panel), la sala no se cae del todo y se puede reintentar desde la consola.
- **Guardia de capacidad** (hecha, `CapacityGuard`): las rotaciones y reconexiones usan el cupo de su propia sala y nunca esperan (`reserve()` es idempotente por sala). Evitar abrir sesiones nuevas de más (reintentos rápidos, rotación sin reanudar).
- Contadores: `rotations`, `resumptions`, `fresh_sessions`, `reconnects`, `errors`, `last_error`, `live_sessions_opened_today`.
- Para probarla con los mp3 cortos: `FileSource` con `loop=True` (T1.1).

**Listo cuando:** corrida de 25 min en loop con ≥ 2 rotaciones: sin caídas, sin frases duplicadas visibles y con huecos < 3 s; el log dice si cada rotación fue reanudación o sesión nueva.

#### T2.2 · Aislamiento multi-sala — A · 25 min · P0 · depende de T2.1

**Técnico:**
- Cada `Session.run` envuelto en `try/except` propio; una excepción no controlada pasa esa sala a `ERROR` sin tocar las demás.
- Prueba: 2 salas corriendo; a una se le pasa un archivo corrupto (o se la detiene de golpe) y la otra sigue emitiendo.

**Listo cuando:** la prueba pasa.

#### T2.3 · Persistencia — A · 20 min · P0

**Estado:** 🟡 `captions.jsonl` hecho con escritor asíncrono (`core/persistence.py`: cola por sala + `asyncio.to_thread`; `tests/test_session.py` prueba que un disco lento no frena a ninguna sala). **Falta `meta.json` y la recarga al reiniciar.**

**Técnico:**
- `DATA_DIR/sessions/<id>/captions.jsonl`: solo eventos **finales**, una línea por evento (hecho).
- `meta.json`: título, orador, idiomas, engine, glosario, `started_at`, `stopped_at`, estado del Knowledge Pack, URL de NotebookLM (si existe).
- Al reiniciar el proceso: cargar las sesiones terminadas desde disco (para que sigan visibles sus exports).
- **Recarga del historial después de un reinicio** (el Space se puede reiniciar en plena charla): al recrear una sala desde `meta.json`, cargar los últimos 50 finales por idioma desde su `captions.jsonl` al historial de `Session`, para que quien reconecta vea lo anterior. Continuar la numeración de `seg` desde el último guardado.

**Listo cuando:** después de parar una sala, los archivos existen y se pueden leer; y después de reiniciar el proceso, un cliente que se conecta a esa sala recibe el historial anterior.

#### T2.4 · Métricas — A · 50 min · P1

**Funcional:** poder decir "la latencia es X" con números reales y detectar problemas antes que el público.

**Técnico (`core/metrics.py`):**
- **Nivel de audio:** RMS por frame en dBFS.
- **Alerta de silencio:** nivel < −50 dBFS durante más de 20 s → `silence_alert=true`.
- **VAD local simple:** voz = nivel > −45 dBFS (ajustable), con 300 ms de "hangover". Registra inicio y fin de cada tramo de voz.
- **Latencia del primer parcial:** inicio de voz → primer interim siguiente. **Latencia del final:** fin de voz → siguiente final. p50 / p95 sobre las últimas 200 muestras (`deque`).
- **Frames:** `last_frame_age_s`, `dropped_frames`.
- **Runner:** exponer `engine.runner.stats` y la edad del último mensaje de Gemini, para detectar una sesión que conecta pero no responde (lo que se vio en T1.4).
- **Event loop:** `loop_lag_ms` de `LoopLagMonitor` (ya en `/healthz`).
- **Cuota:** contador de sesiones Live abiertas hoy, persistido en `DATA_DIR/quota.json`, que se reinicia a medianoche hora del Pacífico (igual que el RPD de Google).
- Oyentes conectados por idioma (desde el `SessionManager`).

**Listo cuando:** `GET /api/sessions` devuelve todas las métricas con valores razonables en una corrida real.

#### T2.5 · API de administración + auth — A · 35 min · P0

**Funcional:** que solo el equipo del evento pueda crear salas y gastar cuota (el Space es público).

**Técnico:**
- `api/auth.py`: dependencia que exige `Authorization: Bearer <ADMIN_TOKEN>` (REST) o `?token=` (WS). Comparación con `hmac.compare_digest`.
- `POST /api/sessions` body: `{title, speaker, source_lang: "en"|"es", source: "mic"|"file", file?: str, loop?: bool, glossary_text?: str}`. `target_lang` se calcula (en↔es).
- `POST /api/uploads`: multipart, solo `audio/*`, máximo 100 MB, se guarda en `DATA_DIR/uploads/`; devuelve el nombre para usar en `file`.
- `GET /api/sessions`: estado completo + métricas (para el panel).
- Validaciones con errores claros (400/404/409). `CapacityError` (cupo Live lleno) → **409** con el mensaje tal cual (`api/errors.py` ya lo mapea). El cuerpo del 409 indica que la sala se puede arrancar en modo browser, y la consola ofrece ese botón (T2.17).

**Listo cuando:** sin token → 401; con token se crean, arrancan y paran salas desde `curl`, y la tercera sala recibe 409.

#### T2.6 · WS de ingesta de audio — B · 25 min · P0 · depende de T1.9

**Técnico:**
- `sources/mic_source.py`: `AudioSource` que alimenta una `FrameQueue(maxsize=50)` (5 s); `push(pcm)` desde el WS; si está llena, descarta el más viejo.
- `/ws/ingest/{id}?token=`: recibe frames binarios de exactamente 3.200 bytes (100 ms de PCM16 LE 16 kHz mono); descarta y cuenta los de otro tamaño.
- Cada 1 s envía al cliente `{"type":"ingest_status","status":"RUNNING","lat_p50_ms":...}` para que la vista de escenario muestre el estado.
- Si no llegan frames durante 3 s: métrica `mic_connected=false`.

**Listo cuando:** un script que manda el mp3 por WS en frames de 100 ms produce subtítulos.

#### T2.7 · Captura de mic con AudioWorklet — B · 1.3 h · P0 · depende de T2.6

**Funcional:** capturar la entrada de la placa de audio desde el browser de la mini PC y mandarla al servidor.

**Técnico (`js/mic.js` + `js/pcm-worklet.js`):**
- `getUserMedia({audio: {deviceId, channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false}})` (los filtros de videollamada degradan la señal de una consola).
- **Selector de dispositivo:** `enumerateDevices()` filtrando `audioinput` (las etiquetas solo aparecen después de dar permiso: pedir primero, listar después).
- `AudioContext` a la tasa nativa; el worklet **remuestrea a 16 kHz** con interpolación lineal.
- Acumular 1.600 muestras (100 ms), convertir Float32 → Int16 con clamp, y enviar con `port.postMessage(buffer, [buffer])` → `ws.send(buffer)`.
- Medidor de nivel local (barra) calculado en el worklet.
- Reconexión del WS con backoff; durante la desconexión, bufferear hasta 3 s y descartar el resto.
- `navigator.wakeLock.request("screen")` para que la pantalla del escenario no se apague.
- El `AudioContext` se crea tras un clic ("Iniciar captura"): los navegadores lo exigen.

**Listo cuando:** en Chrome, hablando al mic de la notebook, aparecen subtítulos en el celular; el selector lista y usa otra entrada de audio.

#### T2.8 · Vista de escenario — B · 50 min · P0 · depende de T2.7, T1.12

**Funcional:** la pantalla frente al público; captura el audio y muestra subtítulos + QR, igual que operan hoy.

**Técnico (`stage.html?s=ID&token=...`):**
- Barra superior chica: nivel de mic, estado de conexión, badge de latencia (p50 del final).
- Centro: subtítulos grandes (reusa `captions.js`), selector de idioma a mostrar.
- Esquina inferior: QR a `location.origin + "/?s=ID&lang=es"` generado client-side con `qrcode.js` (cdnjs) + la URL en texto corto.
- Botón de pantalla completa (`requestFullscreen`).
- Si la fuente es `mic`: botón "Iniciar captura" + selector de dispositivo (T2.7). Si es `file`: solo muestra subtítulos.

**Listo cuando:** en pantalla completa se ve profesional, el QR abre la audiencia correcta y la captura funciona.

#### T2.9 · Consola de operador — B · 50 min · P0 · depende de T2.5

**Funcional:** el equipo de producción crea y controla salas sin tocar código.

**Técnico (`admin.html` + `js/admin.js`):**
- Login: campo para el `ADMIN_TOKEN` (se guarda en `sessionStorage`).
- Formulario "Nueva sala": título, orador, idioma de la charla (EN/ES), fuente (mic / archivo de samples / subir mp3), loop, glosario (textarea: un término por línea, `mal => bien` para reemplazos).
- Lista de salas: estado con color, botones Start / Stop / Borrar, links "Abrir vista de escenario" (con token) y "Abrir audiencia".
- Errores de la API visibles (toast), incluido el 409 sin cupo.

**Listo cuando:** se crea una sala con mic y otra con mp3, se arrancan y se paran desde la consola.

#### T2.10 · Prueba de 2 salas, en 4 pasos — AB · P0

"Dos sesiones conectadas" no es lo mismo que "dos salas funcionando 20 minutos": se valida por capas ([reporte §3](CONCURRENCY-REPORT.md#3-capas-de-prueba)) y cada paso habilita el siguiente.

**T2.10a · 2 sesiones Live aisladas — ✅** Herramientas completas: `scripts/live_probe.py` (SDK crudo) y `scripts/runner_probe.py` (capas `engine` y `session`, con trials, stagger, cooldown, clasificación objetiva, lag del event loop y reporte JSON con branch + commit + fecha). Las corridas del 24/9 quedan como `OBSERVED` ([reporte §5](CONCURRENCY-REPORT.md#5-historial-observed-249-antes-de-esta-revisión)); el barrido repetido, en §6. El veredicto del gate pasa a T2.13.

##### T2.10b · 2 salas con el backend completo, 2–3 min — AB · 15 min · depende de T2.10a, T2.5

**Técnico:** en local, 2 salas creadas por la API (una EN, una ES), con clientes WS de los dos idiomas en cada una. Arrancar tras unos minutos sin uso de la API y registrar `runner.stats` de cada sala. Antes, sin API: `runner_probe --layer session` (misma capa sin HTTP) y `audience_load` (fan-out con replay).

**Listo cuando:** las 2 salas entregan subtítulos en ambos idiomas y ninguna afecta a la otra.

##### T2.10c · 2 salas × 20+ min en el Space — AB · 30 min · depende de T2.10b, T2.1, T2.18

**Técnico:** en el Space (no en local):
- Sala 1: mic en español (una persona habla o se reproduce el mp3 en ES por parlante).
- Sala 2: mp3 en inglés con loop.
- Checklist: subtítulos en ambos idiomas en ambas salas; ≥ 2 rotaciones por sala sin cortes; celular vía QR; ninguna sala afecta a la otra; métricas coherentes.
- Anotar bugs y resolver los bloqueantes antes de seguir.

**Listo cuando:** checklist completo.

##### T2.10d · Rotación/reanudación con 2 salas concurrentes — A · 20 min · depende de T2.10c

**Técnico:** forzar la rotación de las 2 salas cerca del mismo minuto (`ROTATE_AFTER_S` bajo) y verificar que la guardia de capacidad (cada sala conserva su cupo) y la reanudación no dejen a ninguna sala sin sesión.

**Listo cuando:** 3 rotaciones seguidas por sala, con las 2 salas activas, sin huecos > 3 s.

#### T2.11 · Video de emergencia — AB · 30 min · P0

**Técnico:** grabación de pantalla (OBS) de 60–90 s mostrando consola, escenario y celular; subir a YouTube como "no listado".

**Listo cuando:** hay un link de YouTube entregable, aunque sea imperfecto.

#### T2.12 · Corregir la medición de `runner_probe` / `probe_metrics` — A · 40 min · P1

**Funcional:** que el reporte del barrido distinga "Gemini rechazó o no conectó" de "terminó bien", y que no marque degradaciones que no ocurrieron.

**Contexto:** barrido del 25/9, [reporte §6 · Validez de la medición](CONCURRENCY-REPORT.md#validez-de-la-medición).

**Técnico:**
- **(a) Timeout interno mal etiquetado.** En `scripts/runner_probe.py` (`engine_layer`), `except asyncio.TimeoutError` atrapa también un `TimeoutError` del propio engine (desde Python 3.11 son la misma clase). Un fallo de conexión a los ~10 s queda como `outcome="cut at 60s"` con `error=None`, y el chequeo de cuota (`QUOTA_MARKERS`) no lo ve. Fix: distinguir el corte propio (por ejemplo `asyncio.timeout()` + `cm.expired()`, o comparar `elapsed` con `args.seconds`) y guardar `f"{type(e).__name__}: {e}"`. Revisar si `session_layer` tiene el mismo problema.
- **(b) Cierre de 10 s después del corte.** Tras cancelar a los 60 s, el cierre tarda ~10 s más (`elapsed_s` ≈ 70) en 7 de las 24 sesiones (A3 t3, A4-s5 t1 y t3). Medir la ventana hasta el corte (guardar `t_cut`) y registrar aparte `close_s`. Investigar el origen (HYPOTHESIS: timeout de apertura/cierre del websocket del SDK).
- **(c) La cola posterior al corte cuenta como stall.** `probe_metrics.session_metrics` usa `end_s = elapsed_s - connect_ms`, así que el tramo entre el último texto y el fin del cierre entra en `stall_max_s`. Usar `end_s = min(elapsed, seconds) - connect`. Los `dropped` del cierre (la cola se llena mientras nadie consume) tampoco deberían contar: registrar los frames descartados hasta el corte.
- Tests en `tests/test_probe_metrics.py` para (c) y un caso de timeout interno para (a).

**Listo cuando:** re-clasificar los 4 reportes del barrido da A3 t3 y A4-s5 t3 sin `SILENT_DEGRADATION` falsa (su hueco real entre textos es de 2–7,5 s), y un fallo de conexión sale como `error` con el mensaje.

#### T2.13 · Completar el barrido y cerrar el veredicto — A · 1.5 h de reloj (casi todo cooldown) · P1 · depende de T2.12

**Técnico:**
- Nueva línea base A1 (con el probe corregido), intercalada entre bloques.
- Repetir A3 (N=3) con el error capturado: ¿rechazo explícito o timeout?
- A4 con stagger 0, 20 y 30 s (A4-s5 ya corrido).
- Bloque B: `--layer session` con N=2.
- Bloque D: frío vs. caliente (sin cooldown).
- Prueba de audiencia: `audience_load --clients 10,50,100` contra `ENGINE=replay` (reporte §7).
- Mirar en paralelo AI Studio → Rate limits.

**Listo cuando:** el [reporte §8](CONCURRENCY-REPORT.md#8-veredicto) tiene PASS/FAIL con resultados repetidos, y D2 (`MAX_CONCURRENT_LIVE`) pasa de decisión provisional a decisión. Los bloques A4 fijan también el valor de `LIVE_START_GAP_S` (D10, T2.18).

### Fase 2 — Escalado y resiliencia

Camino a 10 salas sin keys extra ([`ARCHITECTURE.md` §6.5](ARCHITECTURE.md#65-camino-a-10-salas)). T2.18 es P0 y va antes de T2.10c; el resto va después de cerrar los P0 de Fase 2.

#### T2.14 · Motor por sala — A · 45 min · P1 · depende de T2.5

**Funcional:** que cada sala elija su motor, para que las que no entran en el cupo Live puedan subtitular igual.

**Técnico:**
- Campo opcional `engine` en `POST /api/sessions`: `live_translate` | `chunked` | `replay` | `external`. Default: `ENGINE`.
- `engine/factory.py` construye el motor por sala (hoy `ENGINE` es global).
- `CapacityGuard` reserva cupo solo si `engine.uses_live`: las salas `external` y `replay` no lo consumen.
- El motor se expone en `GET /api/sessions`, `/api/public/sessions` y `meta.json`.
- Tests: sala `external` con el cupo lleno arranca; sala Live con el cupo lleno → `CapacityError`.

**Listo cuando:** con `MAX_CONCURRENT_LIVE=2`, corren 2 salas Live + 1 `external` sin 409.

#### T2.15 · `/ws/publish` + `ExternalEngine` — A · 40 min · P1 · depende de T2.14

**Funcional:** recibir subtítulos ya hechos (por ejemplo, desde el navegador del escenario) y distribuirlos como si vinieran de Gemini.

**Técnico:**
- `engine/external.py`: `ExternalEngine` con `needs_audio=False` y `uses_live=False`; espera eventos en una `asyncio.Queue` que alimenta el WS y los emite.
- `/ws/publish/{id}?token=`: recibe JSON `{lang, kind: "interim"|"final", text, seg}`. Valida `lang` (idiomas de la sala), `text` ≤ 500 caracteres y `seg` creciente; aplica el glosario de la sala; el servidor pone `t0`/`t1`.
- Pasa por el mismo `Session.emit`: fan-out, historial y `CaptionWriter` sin cambios.
- Cierres: 4401 sin token, 4404 sala inexistente, 4409 si la sala no es `external`.
- Test con cliente WS: publicar 3 eventos → llegan a un cliente de `/ws/captions` y a `captions.jsonl` (solo finales).

**Listo cuando:** un script que publica un jsonl por WS hace que la audiencia vea los subtítulos.

#### T2.16 · `stage.html` modo browser — B · 1.2 h · P1 · depende de T2.15, T2.8

**Funcional:** que la mini PC del escenario haga los subtítulos con el motor del navegador cuando la sala no tiene cupo Live.

**Técnico (`js/browser-engine.js`):**
- Feature detection: `SpeechRecognition || webkitSpeechRecognition` y `Translator` (Chrome de escritorio). Sin reconocimiento: el modo no se ofrece.
- Reconocimiento con `continuous = true`, `interimResults = true`, `lang` = `en-US` / `es-ES`; se reinicia en `onend` (Chrome lo corta solo); `seg` incremental.
- Finales traducidos con la Translator API. La descarga del modelo se dispara con el clic de "Iniciar"; se muestra el progreso.
- Sin Translator: publica solo el idioma original y avisa en la barra superior.
- Publica en `/ws/publish/{id}` con reconexión y backoff (reusa el de T2.7). Badge "Motor: navegador".

**Listo cuando:** en Chrome de escritorio, hablando al mic, la audiencia ve original + traducción.

#### T2.17 · Degradación a browser — AB · 30 min · P1 · depende de T2.16, T2.9, T2.5

**Funcional:** si una sala no consigue cupo Live o se cae, el operador la pasa a modo navegador con un clic, sin perder lo ya subtitulado.

**Técnico:**
- `POST /api/sessions/{id}/engine` body `{engine: "external" | "live_translate"}`: para el motor actual, libera el cupo Live, conserva el historial, `captions.jsonl` y la numeración de `seg`, y arranca el nuevo motor.
- `session_status` incluye `engine`: la vista de escenario cambia sola a modo browser (T2.16) o vuelve a mandar audio.
- Consola: ante un 409 al arrancar o una sala en `ERROR`, botón "Pasar a modo navegador". Botón inverso "Volver a Live" si hay cupo (si no, 409).
- **Nunca automática** (D14): el backend no cambia de motor solo.

**Listo cuando:** con 2 salas Live, la tercera recibe 409 y con un clic queda subtitulando en modo browser, sin que la audiencia tenga que reconectar.

#### T2.18 · Arranque escalonado de sesiones Live — A · 30 min · P0 · depende de T2.5

**Funcional:** que abrir varias salas a la vez no degrade a ninguna (en T2.10a, abrir sesiones cerca hizo a una de ellas 3–7× más lenta sin dar error).

**Técnico:**
- Primero el chequeo de cupo (`CapacityGuard`, sin cambios: rechaza, **no encola**, D3); después, la espera del gap.
- En `SessionManager`: un `asyncio.Lock` + `last_live_open_at` (monotónico) global. Cada apertura de conexión Live (arranque, sesión nueva del fallback de rotación, reconexión) espera hasta que pasen `LIVE_START_GAP_S` desde la anterior.
- Se inyecta como callable opcional `live_gate` en `SessionContext` (`backend/engine/base.py`); `LiveSessionRunner` lo llama antes de `connect`.
- Mientras espera, la sala muestra `STARTING` con "esperando turno (Xs)".
- `LIVE_START_GAP_S`: default provisional **20 s**; `0` lo desactiva. El valor se fija con los bloques A4 de T2.13 (D10). Agregarlo a `.env.example` y al README en el mismo commit.
- Tests con reloj falso: dos arranques seguidos → el segundo abre ≥ gap después; la rotación de una sala y el arranque de otra también se espacian.

**Listo cuando:** los tests pasan y 2 salas arrancadas a la vez en local abren sus conexiones separadas por el gap (visible en el log).

#### T2.19 · Fan-out eficiente — A · 40 min · P1 · depende de la prueba de audiencia de T2.13

**Funcional:** que una sala con cientos de oyentes no cargue el event loop que comparten todas las salas.

**Técnico:**
- `Session.emit` serializa el evento **una vez** (`json.dumps`) y las colas por cliente guardan el string; el WS usa `send_text`.
- Throttle de interims por sala e idioma a `INTERIM_MAX_HZ`: gana el último interim; los finales nunca se limitan. Default `0` = sin límite hasta que la prueba de audiencia o el test E digan otra cosa (D9). Agregarlo a `.env.example` y al README.
- Tests: un evento con N clientes se serializa una sola vez; con `INTERIM_MAX_HZ=4`, 20 interims en 1 s salen como ≤ 4 + el final.

**Listo cuando:** los tests pasan y `audience_load` no empeora CPU ni latencia respecto de la corrida de T2.13.

#### T2.20 · Test E: 10 salas × 100 clientes — AB · 30 min · P1 · depende de T2.13 (y de T2.19, si se hizo)

**Funcional:** saber si un Space aguanta la audiencia de 10 salas, sin gastar cupo de Gemini.

**Técnico:**
- En el Space (no en local): `ENGINE=replay`, `DEMO_ROOMS=10`, y `python -m scripts.audience_load --clients 1000 --seconds 300 --server-pid <pid>`. Verificar que los clientes se repartan parejo entre las 10 salas (`--rooms` ya existe; si no reparte, agregar el reparto).
- Medir: mensajes entregados/perdidos por cliente, latencia servidor → cliente p50/p95, lag del event loop (`/healthz`), CPU y RSS.
- Registrar como RESULT en el [reporte §7](CONCURRENCY-REPORT.md#7-prueba-de-audiencia-sin-gemini), con branch + commit + fecha.

**Listo cuando:** el reporte tiene el veredicto: el Space alcanza (p95 < 1 s y lag < 100 ms), hace falta T2.19, o hace falta T3.13.

#### T2.21 · Render incremental — B · 40 min · P1 · depende de T1.12

**Funcional:** que la página de audiencia siga fluida en celulares de gama baja durante una charla entera.

**Técnico (`js/captions.js`):**
- Mapa `seg` → nodo del DOM: un interim actualiza `textContent` de su nodo; un final lo fija o agrega uno nuevo. Nada de re-renderizar la lista entera.
- DOM acotado: como máximo ~200 líneas; se borran las más viejas.
- Agrupar las actualizaciones con `requestAnimationFrame`.

**Listo cuando:** 40 min de replay en un celular sin long tasks > 50 ms (panel Performance) y con el DOM acotado.

### Fase 3 — Integración, UX y datos de prueba (H8 → H12.5)

#### T3.1 · Modo overlay — B · 35 min · P1

**Funcional:** subtítulos traducidos quemados en el stream (pain point confirmado por la organización).

**Técnico:**
- Misma `index.html` con `?s=ID&lang=es&overlay=1&bg=transparent|green&size=L&lines=2`.
- Fondo transparente (o verde chroma), sin UI, texto blanco con contorno negro (`text-shadow` en 4 direcciones), centrado abajo.
- Probar en OBS: Browser Source 1920×1080 con la URL.
- Documentar en el README cómo cargarlo en OBS y en vMix (entrada Web Browser).

**Listo cuando:** en OBS se ven los subtítulos sobre un video de prueba.

#### T3.2 · Panel de monitoreo — B · 1 h · P1 · depende de T2.4

**Funcional:** el equipo ve de un vistazo si alguna sala tiene problemas.

**Técnico:**
- Sección en `admin.html`, alimentada por `/ws/admin` (snapshot cada 1 s).
- Por sala: estado (color), fuente, tiempo activo, nivel de mic + antigüedad del último frame, alerta de silencio, latencia p50/p95 (parcial y final), rotaciones, reconexiones, último error, oyentes por idioma.
- Global: sesiones Live abiertas vs. `MAX_CONCURRENT_LIVE` (`manager.live_usage()`), sesiones hoy vs. `QUOTA_LIVE_SESSIONS_PER_DAY`, lag del event loop, costo acumulado **USD 0**.
- Resaltar en rojo: `ERROR`, silencio, mic desconectado, cuota > 80%.

**Listo cuando:** desenchufar el mic (o parar el envío) se refleja en el panel en < 5 s.

#### T3.3 · Exports — A · 45 min · P1 · depende de T2.3

**Funcional:** al terminar, descargar la transcripción completa en formatos estándar.

**Técnico (`post/exports.py`):**
- Fuente: `captions.jsonl` (finales).
- Armado de cues: máximo 42 caracteres por línea, 2 líneas, 7 s; mínimo 1 s. Los finales largos se parten y el tiempo se reparte proporcional a los caracteres.
- Offset: restar la latencia p50 medida a cada timestamp (para alinear con el audio grabado).
- Formatos: SRT (`00:01:02,500`), VTT (`00:01:02.500`, cabecera `WEBVTT`), TXT (texto corrido), MD (metadata + transcripción en ambos idiomas con marcas `[mm:ss]`).
- `tests/test_exports.py` para el formateo de tiempos y el partido de cues.

**Listo cuando:** el VTT exportado se carga en un reproductor y queda razonablemente sincronizado.

#### T3.4 · Knowledge Pack — A · 50 min · P1 · depende de T2.3

**Funcional:** la charla se convierte sola en resumen, puntos clave y quiz.

**Técnico (`post/knowledge.py`):**
- Se dispara en segundo plano al hacer Stop (`kp_status: pending → ready | error`).
- Transcripción con marcas `[mm:ss]` (~10k tokens para 40 min: entra entera).
- Una llamada a `KP_MODEL` con `response_mime_type="application/json"` y `response_schema`:
  - `summary_es`, `summary_en` (5–7 oraciones)
  - `key_points`: lista de `{t: "mm:ss", es, en}` (5–8)
  - `terms`: términos técnicos mencionados
  - `quiz`: 5 × `{q_es, q_en, options_es[4], options_en[4], answer_idx, explanation_es, explanation_en}`
- Guardar en `knowledge.json`. Ante 429, reintentar una vez a los 60 s; si falla, `kp_status=error` (los exports siguen disponibles).

**Listo cuando:** al parar una sala de prueba, en < 1 min existe un `knowledge.json` válido.

#### T3.5 · Página de la charla — B · 1.2 h · P1 · depende de T3.3, T3.4

**Funcional:** después de la charla, el mismo QR lleva al resumen, quiz, descargas y preguntas.

**Técnico (`talk.html?s=ID`):**
- Resumen con selector ES/EN; puntos clave con su `[mm:ss]`.
- Quiz interactivo: elegir respuestas, ver puntaje y explicación.
- Descargas: SRT, VTT, TXT, MD por idioma.
- Botón **"Copiar para NotebookLM"**: copia el MD al portapapeles y abre `https://notebooklm.google.com` en otra pestaña.
- Caja "Preguntale a la charla" (T3.6).
- Si existe `notebooklm_url` (T3.9), botón "Abrir notebook con podcast".
- En la página de audiencia: al recibir `session_status=STOPPED`, mostrar "La charla terminó → ver resumen" con link a `talk.html`.
- Mientras `kp_status=pending`, mostrar "Generando resumen…" con reintento cada 5 s.

**Listo cuando:** flujo completo desde el celular: subtítulos → stop → resumen y quiz.

#### T3.6 · "Preguntale a la charla" — A · 30 min · P1 · depende de T3.4

**Técnico:**
- `POST /api/sessions/{id}/ask` body `{q}` (máximo 300 caracteres).
- Prompt: responder **solo** con información de la transcripción, en el idioma de la pregunta, citando `[mm:ss]`; si no está en la charla, decirlo.
- Rate limit en memoria: 5 preguntas cada 10 min por IP (IP real vía `X-Forwarded-For`, habilitado con `--proxy-headers`).
- Cache por pregunta normalizada (minúsculas, sin puntuación).
- Ante 429 de Gemini: mensaje amable "Mucha demanda, probá en un minuto".

**Listo cuando:** 3 preguntas de prueba responden con minuto citado y la sexta pregunta seguida devuelve el límite.

#### T3.7 · Pasada final de calidad — A · 30 min · P2

**Técnico:** al hacer Stop, una llamada por idioma a `KP_MODEL` con la transcripción + glosario completo para corregir errores de reconocimiento y traducción, conservando las marcas de tiempo. Si existe, los exports ofrecen "versión revisada" además de la "versión en vivo".

**Listo cuando:** el export revisado corrige al menos los términos del glosario.

#### T3.8 · Audio traducido (solo Camino 1) — A · 1.5 h · P2

**Funcional:** escuchar la traducción con auriculares desde el celular.

**Técnico:**
- El runner ya recibe audio PCM 24 kHz; reenviarlo a `/ws/audio/{id}?lang=` como frames binarios.
- En la audiencia, botón "🎧 Escuchar" (requiere clic): `AudioContext` a 24 kHz, cola de reproducción con ~300 ms de colchón, cada chunk programado con `source.start(nextTime)`.
- Si el cliente se atrasa más de 2 s, descartar audio viejo y resincronizar.

**Listo cuando:** en el celular se escucha la traducción con retraso estable.

#### T3.9 · Exporter automático a NotebookLM — A · 1.5 h (timebox) · P2

**Funcional:** al terminar la charla, se crea sola un notebook con la transcripción y un podcast.

**Técnico (`post/notebooklm.py`, librería no oficial `notebooklm-py`):**
- Local: `pip install notebooklm-py` y `notebooklm login` (abre el navegador y guarda la sesión).
- Script `tools/notebooklm_export.py <session_id>`: crear notebook "Nerdearla 2026 — <título>", agregar la transcripción MD como fuente de texto, generar el Audio Overview y esperar a que termine. **Verificar en el README de la librería** los nombres exactos de los métodos.
- Probarlo primero a mano desde local. Si funciona, habilitarlo en el Space: guardar el JSON de sesión como secret `NOTEBOOKLM_STORAGE_JSON`, escribirlo a un archivo al arrancar, y llamar al exporter en el Stop solo si `NOTEBOOKLM_ENABLED=1`.
- Nunca bloquear el Stop: corre en segundo plano y cualquier error solo se loguea.
- **Si a las 1.5 h no funciona, se abandona** (las capas 1 y 3 ya cubren la idea).

**Listo cuando:** al parar una sala, `meta.json` tiene `notebooklm_url` y el link funciona.

#### T3.10 · `docker-compose.yml` + túnel opcional — A · 20 min · P1

**Técnico:**
- Servicio `app`: `build: .`, `ports: ["7860:7860"]`, `env_file: .env`, volumen `./data:/home/user/app/data`.
- Servicio `tunnel` bajo el perfil `tunnel`: imagen `cloudflare/cloudflared`, comando `tunnel --url http://app:7860`.
- Uso documentado: `docker compose up` y `docker compose --profile tunnel up`.

**Listo cuando:** en una máquina limpia, `docker compose up` levanta la app en `localhost:7860`.

#### T3.11 · Samples, glosario default, replay real — AB · 20 min · P0

**Técnico:**
- Los 2 mp3 recortados ya están (`samples/en_talk_3min.mp3`, `samples/es_talk_2min.mp3`).
- `config/glossary.default.json` con términos de las charlas de prueba + Nerdearla.
- Reemplazar `samples/replay_demo.jsonl` por el `captions.jsonl` de una corrida real buena.

**Listo cuando:** los tres elementos están commiteados y el replay usa datos reales.

#### T3.12 · README completo — B · 1 h · P0 (A revisa)

**Secciones:**
1. Qué es (2 párrafos) + GIF o captura.
2. Probalo en 3 minutos: Duplicate this Space → secrets → `/admin.html` → sala con sample → abrir audiencia.
3. Arquitectura en corto + link a [`ARCHITECTURE.md`](ARCHITECTURE.md).
4. Cómo crear la API key **sin billing** y cómo chequear cuotas en AI Studio.
5. Variables de entorno (tabla).
6. Operación en un evento: mic por placa de audio en Chrome, vista de escenario, QR, overlay en OBS/vMix, panel.
7. Después de la charla: exports, Knowledge Pack, NotebookLM.
8. Self-host: `docker compose` y túnel.
9. Cómo escalar: motor por sala (Live + browser), arranque escalonado, billing opcional, Durable Objects para audiencias grandes, límites del free tier, modo local (roadmap). Nunca varias keys propias.
10. Métricas medidas (resumen de T1.4 + latencias de T2.10).
11. Privacidad: en free tier Google usa el contenido para mejorar sus productos.
12. Licencia MIT y créditos.

Ya está la base (índice de documentación, correr en local, CLI, deploy, variables, muestras, privacidad, licencia); ver también la [checklist de §6](#checklist-del-readme-final).

**Listo cuando:** alguien que no conoce el proyecto puede deployarlo solo con el README (se valida en T4.1).

#### T3.13 · Audiencia en Durable Objects — A · 3 h · P2 · depende de T2.20

**Funcional:** sacar del Space el fan-out a la audiencia cuando son miles de oyentes, sin tocar el motor.

**Contexto:** [`ARCHITECTURE.md` §6.4](ARCHITECTURE.md#64-durable-objects-qué-resuelve-y-qué-no) y [`alternatives/CLOUD-EDGE.md`](alternatives/CLOUD-EDGE.md). Solo si el test E (T2.20) muestra límites. El motor sigue en Python (D11, D12).

**Técnico:**
- Worker de Cloudflare + un Durable Object por sala (`idFromName(session_id)`), con la WebSocket Hibernation API para las conexiones de audiencia.
- El backend Python publica cada `CaptionEvent` al DO de su sala: una conexión saliente por sala, con reconexión.
- El DO guarda los últimos 50 finales por idioma (para quien entra tarde) y reenvía por idioma, con el mismo protocolo que `/ws/captions`.
- El frontend usa `AUDIENCE_WS_URL` si está definida; vacía (default) = el mismo servidor. Agregarla a `.env.example` y al README.

**Listo cuando:** con `AUDIENCE_WS_URL` configurada, la audiencia recibe subtítulos desde el edge y el test E contra el DO sale bien.

### Fase 4 — Testing, freeze y pitch (H12.5 → H15)

#### T4.1 · E2E desde cero — AB · 30 min · P0

**Técnico:** simular otra conferencia: con otra cuenta de HF (o un Space nuevo), seguir **solo el README**: duplicar, cargar secrets, crear 2 salas, ver subtítulos en el celular, parar, ver el resumen. Corregir cada hueco de documentación encontrado.

**Listo cuando:** el flujo completo sale sin preguntarle nada al equipo.

#### T4.2 · Hardening y caminos de error — AB · 25 min · P0

**Técnico:** verificar que cada error tenga un mensaje claro:
- API key inválida → sala en `ERROR` con mensaje legible en el panel.
- Sin cupo Live → 409 visible en la consola.
- Permiso de mic denegado → aviso en la vista de escenario.
- Archivo que no es audio → 400 en la consola.
- Sala inexistente en la audiencia → mensaje "Sala no encontrada".
- Repetir la prueba de 2 salas × 20 min (T2.10c) después del último merge.

**Listo cuando:** todos los casos probados.

#### T4.3 · Code freeze + tag — AB · 5 min · P0

**Técnico:** a las **H13.5**, `git tag v1.0.0` y push a GitHub y deploy al Space. Desde acá solo bugfixes.

#### T4.4 · Video final — AB · 1 h · P0

**Técnico:**
- Guion (1–2 min): ver [§6](#video-demo-12-min). Usar audio de una charla de Nerdearla.
- Grabar por tramos con OBS; si algo falla en vivo, usar `ENGINE=replay` para la toma.
- Subtítulos propios: crear una sala con el audio final del video como archivo (`source_lang` = idioma de la narración) → exportar VTT en inglés (y en español) → subirlos a YouTube como subtítulos.
- Subir el video como público o no listado.

**Listo cuando:** video en YouTube con subtítulos en inglés generados por el sistema.

#### T4.5 · Envío a Devpost — AB · 30 min · P0

**Técnico:**
- Título, tagline, descripción (problema, solución, arquitectura, costo cero, cómo escalar, próximos pasos), link al video, link al repo, link al Space, capturas (escenario, celular, overlay, panel, página de la charla).
- Enviar con al menos **1 h de margen antes de las 15:00 UTC** (12:00 ART) y verificar que el envío figure como completo.

**Listo cuando:** Devpost muestra el proyecto enviado.

---

## 6. Entrega

### Video demo (1–2 min)

No hay presentación en vivo: el video + el Devpost son el pitch.

| Tiempo | Contenido |
|---|---|
| 0:00 | El problema: 30+ charlas en inglés, herramientas caras y manuales |
| 0:15 | Consola con 2 salas → celular vía QR → subtítulos con badge de latencia |
| 0:45 | Overlay en OBS sobre el stream |
| 1:05 | Panel de monitoreo: 2 salas, latencia, costo USD 0 |
| 1:20 | Stop → Knowledge Pack + una pregunta respondida con minuto citado |
| 1:45 | "Duplicate this Space" + licencia MIT |

### Checklist del README final

- [ ] Deploy en 2 clics (Duplicate Space) y alternativa `docker compose up`.
- [ ] Cómo crear la API key en un proyecto **sin billing** y cómo chequear cuotas en AI Studio.
- [x] Aviso de uso de datos en free tier.
- [ ] Cómo usar MicSource (placa de audio → browser) y cómo probar con los mp3.
- [ ] Cómo usar el QR y el overlay en OBS/vMix.
- [ ] Cómo escalar: motor por sala (Live + browser), arranque escalonado, billing si hay presupuesto, Durable Objects para audiencias grandes; límites del free tier; modo local (roadmap). Nunca varias keys propias.
- [x] Licencia MIT.

---

## 7. Riesgos y plan B

### Orden de recorte si falta tiempo

1. T3.8 audio traducido, T3.9 NotebookLM automático y T3.13 Durable Objects.
2. T3.7 pasada final.
3. T2.20 test E y T2.19 fan-out eficiente (queda la prueba de audiencia de T2.13).
4. T2.14–T2.17 modo browser (queda el 409 claro).
5. T2.21 render incremental.
6. Quiz dentro de T3.4/T3.5 (quedan resumen + "Preguntale a la charla").
7. T3.2 panel → tabla simple con `GET /api/sessions` refrescada cada 2 s.

**Nunca se recorta:** T2.7 mic, T2.10a–c dos salas, T2.18 arranque escalonado, EN↔ES, T1.12 audiencia, T3.12 README, T1.13 deploy, T4.4 video, T4.5 envío.

### Fallas

| Riesgo | Plan B |
|---|---|
| El cupo de sesiones Live no alcanza para 2 salas | Bajar `MAX_CONCURRENT_LIVE` a 1 (la guardia rechaza la segunda con 409, sin degradar la primera) y pasar la otra sala a modo browser con un clic (T2.17). Camino 2 si transcribe-live tiene otro cupo (HYPOTHESIS). Pool de keys de proyectos propios: **descartado** ([decisiones](ARCHITECTURE.md#decisiones-descartadas-y-por-qué)) |
| Una sesión se degrada en silencio (10+ s sin texto) | Pasó en el barrido incluso con 1 sesión (reporte §6). La alerta de "sesión que conecta pero no responde" (T2.4) la hace visible; la rotación con reanudación (T2.1) es la salida |
| Se agota la cuota diaria en plena demo | Modo replay para grabar el video sin API |
| El modelo preview cambia o falla | Cambiar de camino con el flag `ENGINE=` (misma interfaz) |
| La rotación de 10 min se rompe | Prueba obligatoria de 20+ min antes del freeze (T2.10c) |
| El Space está dormido o se reinicia (disco efímero) | Despertarlo antes de la charla; descargar exports al hacer stop |
| El Space se reinicia en plena charla | Recarga del historial desde `captions.jsonl` (T2.3): quien reconecta ve lo anterior. El operador re-arranca la sala (reanudación si el handle sigue vigente, si no, sesión nueva); si no hay cupo, modo browser (T2.17) |
| Una audiencia masiva satura el Space (fan-out, CPU, lag del loop) | Se mide antes con el test E (T2.20). Primero T2.19 (JSON una vez, throttle de interims) y T2.21; si no alcanza, `AUDIENCE_WS_URL` + Durable Objects (T3.13) |
| El mic no captura | Requiere HTTPS (HF lo da) o localhost |
| Mic desenchufado en pleno evento | Alerta de silencio en el panel |
| NotebookLM no oficial se rompe | Las capas 1 y 3 no dependen de eso |
