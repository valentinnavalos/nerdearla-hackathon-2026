# TASKS — Backlog completo (Nerdearla Vibeathon 2026)

> Complementa a `PLAN.md`. Arquitectura: **opción B (Gemini Live API), Camino 1 o 2**, hosteada en **Hugging Face Spaces**, con A (chunks) como fallback de emergencia.
> Cada tarea tiene: dueño, estimación, prioridad, dependencias, qué hace (funcional), cómo se hace (técnico) y cuándo está lista.

**Dueños:** **A** = motor / backend Python · **B** = web / deploy · **AB** = ambos
**Prioridad:** **P0** = MVP intocable · **P1** = importante para el jurado · **P2** = stretch (se recorta primero)
**Tiempos:** relativos al arranque (H0). Checkpoints de sincronización: **H3.5**, **H8**, **H12.5**.

---

## Tablero resumen

| ID | Tarea | Dueño | Est. | Prio | Fase |
|---|---|---|---|---|---|
| T0.1 | Proyecto y API key sin billing | AB | 15 min | P0 | 0 |
| T0.2 | Relevar cuotas + prueba cualitativa en AI Studio | A | 20 min | P0 | 0 |
| T0.3 | Decidir Camino 1 o 2 | AB | 5 min | P0 | 0 |
| T0.4 | Estructura del repo, `.env.example`, Makefile | B | 20 min | P0 | 0 |
| T0.5 | Congelar contratos (evento, Engine, endpoints) | AB | 20 min | P0 | 0 |
| T1.1 | Fix `FileSource`: productor/consumidor, pacing, loop | A | 25 min | P0 | 1 |
| T1.2 | Actualizar `google-genai` y verificar features | A | 10 min | P0 | 1 |
| T1.3 | `LiveSessionRunner` v0 + CLI | A | 45 min | P0 | 1 |
| T1.4 | Spike de mediciones | A | 30 min | P0 | 1 |
| T1.5 | Engine del camino elegido | A | 45 min | P0 | 1 |
| T1.6 | Traductor local Argos (solo Camino 2) | A | 30 min | P0* | 1 |
| T1.7 | Módulo de glosario | A | 20 min | P0 | 1 |
| T1.8 | Esqueleto FastAPI + config | B | 20 min | P0 | 1 |
| T1.9 | `SessionManager` + `Session` + pub/sub | B | 40 min | P0 | 1 |
| T1.10 | `ReplayEngine` + jsonl de ejemplo | B | 20 min | P0 | 1 |
| T1.11 | WS de captions | B | 20 min | P0 | 1 |
| T1.12 | Página de audiencia v0 | B | 40 min | P0 | 1 |
| T1.13 | Dockerfile HF + primer deploy | B | 40 min | P0 | 1 |
| T1.14 | Integración checkpoint H3.5 | AB | 15 min | P0 | 1 |
| T2.1 | Rotación + resiliencia del runner | A | 1.5 h | P0 | 2 |
| T2.2 | Aislamiento multi-sala | A | 25 min | P0 | 2 |
| T2.3 | Persistencia (`captions.jsonl`, `meta.json`) | A | 20 min | P0 | 2 |
| T2.4 | Métricas: nivel, silencio, latencia, cuota | A | 50 min | P1 | 2 |
| T2.5 | API de administración + auth | A | 35 min | P0 | 2 |
| T2.6 | WS de ingesta de audio (backend del mic) | B | 25 min | P0 | 2 |
| T2.7 | Captura de mic con AudioWorklet | B | 1.3 h | P0 | 2 |
| T2.8 | Vista de escenario (captura + subtítulos + QR) | B | 50 min | P0 | 2 |
| T2.9 | Consola de operador | B | 50 min | P0 | 2 |
| T2.10 | Prueba integrada 2 salas × 20 min | AB | 30 min | P0 | 2 |
| T2.11 | Video de emergencia | AB | 30 min | P0 | 2 |
| T3.1 | Modo overlay para OBS/vMix | B | 35 min | P1 | 3 |
| T3.2 | Panel de monitoreo | B | 1 h | P1 | 3 |
| T3.3 | Exports SRT / VTT / TXT / MD | A | 45 min | P1 | 3 |
| T3.4 | Knowledge Pack (generación) | A | 50 min | P1 | 3 |
| T3.5 | Página de la charla (post-talk) | B | 1.2 h | P1 | 3 |
| T3.6 | "Preguntale a la charla" | A | 30 min | P1 | 3 |
| T3.7 | Pasada final de calidad con glosario | A | 30 min | P2 | 3 |
| T3.8 | Audio traducido (solo Camino 1) | A | 1.5 h | P2 | 3 |
| T3.9 | Exporter automático a NotebookLM | A | 1.5 h (timebox) | P2 | 3 |
| T3.10 | `docker-compose.yml` + túnel opcional | A | 20 min | P1 | 3 |
| T3.11 | Samples, glosario default, replay real | AB | 20 min | P0 | 3 |
| T3.12 | README completo | B | 1 h | P0 | 3 |
| T4.1 | E2E desde cero (otra conferencia) | AB | 30 min | P0 | 4 |
| T4.2 | Hardening y caminos de error | AB | 25 min | P0 | 4 |
| T4.3 | Code freeze + tag | AB | 5 min | P0 | 4 |
| T4.4 | Video final con subtítulos propios | AB | 1 h | P0 | 4 |
| T4.5 | Envío a Devpost | AB | 30 min | P0 | 4 |

\* T1.6 es P0 solo si se elige el Camino 2; si es Camino 1, no se hace.

**Camino crítico:** T0.1 → T0.5 → T1.3 → T1.5 → T1.14 → T2.1 → T2.10 → T4.1 → T4.4 → T4.5.
Todo lo de B corre en paralelo gracias a `ReplayEngine` (T1.10), que simula el motor.

---

## Estructura objetivo del repo

```
backend/
  app.py                 # FastAPI: rutas, static, lifespan
  config.py              # Settings (pydantic-settings)
  main_cli.py            # CLI existente (se actualiza)
  api/
    sessions.py          # REST admin + público
    ws.py                # WS ingest / captions / admin / audio
    auth.py              # dependencia ADMIN_TOKEN
  core/
    events.py            # CaptionEvent, StatusEvent
    session.py           # Session (stage worker)
    manager.py           # SessionManager
    glossary.py          # carga y aplicación del glosario
    metrics.py           # nivel, VAD local, latencias, cuota
    dedupe.py            # dedupe_overlap()
    segmenter.py         # fragmentos -> interim/final (Camino 1)
  sources/
    base.py              # existente
    file_source.py       # existente (se arregla)
    mic_source.py        # nuevo: alimentado por WS
  pipeline/
    normalize.py         # existente
    chunker.py           # existente (fallback A)
  engine/
    base.py              # Engine ABC
    live_runner.py       # LiveSessionRunner (conexión + rotación)
    live_translate.py    # Camino 1
    transcribe_mt.py     # Camino 2
    chunked.py           # ex gemini.py (fallback A)
    replay.py            # ReplayEngine
  translate/
    argos_mt.py          # Camino 2
  post/
    exports.py           # SRT/VTT/TXT/MD
    knowledge.py         # Knowledge Pack + ask
    notebooklm.py        # opcional (P2)
frontend/
  index.html             # audiencia (lista + subtítulos + overlay)
  stage.html             # vista de escenario
  admin.html             # consola de operador + panel
  talk.html              # página post-charla
  js/ common.js captions.js mic.js pcm-worklet.js admin.js talk.js
  css/ style.css
config/glossary.default.json
samples/                 # mp3 recortados + replay_demo.jsonl
scripts/install_argos.py
tests/                   # pytest de funciones puras
Dockerfile
docker-compose.yml
Makefile
README.md  PLAN.md  TASKS.md  LICENSE
```

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | — | Key de un proyecto **sin billing** |
| `ENGINE` | `live_translate` | `live_translate` (Camino 1) · `transcribe_mt` (Camino 2) · `chunked` (fallback A) · `replay` |
| `ADMIN_TOKEN` | — | Protege consola, API admin e ingesta de audio |
| `DATA_DIR` | `./data` | Sesiones, uploads, cuota |
| `LIVE_TRANSLATE_MODEL` | `gemini-3.5-live-translate-preview` | Camino 1 |
| `TRANSCRIBE_MODEL` | `gemini-3.5-transcribe-live` | Camino 2 |
| `KP_MODEL` | `gemini-3.1-flash-lite` | Knowledge Pack, ask, pasada final |
| `MAX_CONCURRENT_LIVE` | `2` | Tope de sesiones Live abiertas en el proceso (ajustar al cupo real) |
| `ROTATE_AFTER_S` | `540` | Rotación preventiva (9 min) |
| `QUOTA_LIVE_SESSIONS_PER_DAY` | `0` | Cupo diario relevado en T0.2 (0 = no mostrar) |
| `NOTEBOOKLM_ENABLED` | `0` | Exporter no oficial (P2) |
| `LOG_LEVEL` | `INFO` | |

---

## Convenciones de trabajo

- `main` siempre deployable. Commits chicos y frecuentes; cada uno debe dejar el Space funcionando.
- Deploy manual: `make deploy` (= `git push hf main`). Cada checkpoint se valida **en el Space**, no en local.
- Nunca commitear `.env` ni keys. Nunca loguear la API key.
- Toda variable nueva se agrega a `.env.example` y a la tabla del README en el mismo commit.
- Si una tarea supera su estimación en más de 50%, avisar al otro y decidir: seguir, simplificar o recortar.

---

## Fase 0 — Preparación (H0 → H0.75)

### T0.1 · Proyecto y API key sin billing — AB · 15 min · P0

**Estado:** ✅ Completo

**Funcional:** tener credenciales de Gemini que nunca generen cobros.

**Técnico:**
- En AI Studio, crear un **proyecto nuevo** (no reutilizar el que tiene billing).
- Generar la API key en ese proyecto.
- Verificar en AI Studio → Projects que el proyecto figure como **Free**.
- Cargar la key en el `.env` local de ambos.

**Listo cuando:** ambos tienen la key y el proyecto figura en tier Free.

### T0.2 · Relevar cuotas + prueba cualitativa — A · 20 min · P0 · depende de T0.1

**Estado:** ✅ Completo

**Funcional:** saber cuántas salas simultáneas y cuántas horas por día soporta el free tier.

**Técnico:**
- AI Studio → Rate limits. Anotar sesiones concurrentes, RPM, TPM y RPD de:
  - `gemini-3.5-live-translate-preview`
  - `gemini-3.5-transcribe-live`
  - `gemini-3.1-flash-lite`
  - Gemma 4
- En AI Studio → Live, probar 2 min cada modelo reproduciendo un mp3 por parlante cerca del mic. Evaluar a oído calidad de transcripción y traducción, sobre todo términos técnicos.
- Registrar todo en `PLAN.md` §8.

**Listo cuando:** la tabla de cuotas está completa en `PLAN.md`.

### T0.3 · Decidir Camino 1 o 2 — AB · 5 min · P0 · depende de T0.2

**Estado:** ✅ Completo — Camino 1 (`ENGINE=live_translate`), ver `PLAN.md §8`

**Técnico:** aplicar la tabla de decisión de `PLAN.md` §2.3:
- live-translate con ≥ 2 sesiones concurrentes y cupo diario suficiente → **Camino 1** (`ENGINE=live_translate`).
- Si no, transcribe-live disponible → **Camino 2** (`ENGINE=transcribe_mt`).
- Fijar `MAX_CONCURRENT_LIVE` al cupo concurrente real.

**Listo cuando:** la decisión está escrita en `PLAN.md` y en el default de `ENGINE`.

### T0.4 · Estructura del repo, `.env.example`, Makefile — B · 20 min · P0

**Técnico:**
- Crear carpetas y archivos vacíos según "Estructura objetivo". Renombrar `engine/gemini.py` → `engine/chunked.py`.
- `.env.example` con todas las variables de la tabla.
- `.gitignore`: `.env`, `data/`, `__pycache__/`, `*.wav`.
- `Makefile`:
  - `make dev` → `uvicorn backend.app:app --reload --port 7860`
  - `make test` → `pytest -q`
  - `make deploy` → `git push hf main`
  - `make cli F=samples/x.mp3` → CLI

**Listo cuando:** `make dev` levanta (aunque devuelva 404) y `make test` corre sin errores.

### T0.5 · Congelar contratos — AB · 20 min · P0

**Funcional:** que A y B puedan trabajar en paralelo sin pisarse.

**Técnico:**
- `core/events.py` (pydantic):

```python
class CaptionEvent(BaseModel):
    type: Literal["caption"] = "caption"
    session_id: str
    lang: Literal["en", "es"]
    kind: Literal["orig", "trans"]
    seg: int                 # id de segmento por (session, lang); interim y final comparten seg
    final: bool
    text: str
    t0: float                # segundos desde el start de la sesión
    t1: float
    lat_ms: int | None = None
```

- `engine/base.py`:

```python
class Engine(ABC):
    @abstractmethod
    async def run(self, frames: AsyncIterator[AudioFrame],
                  emit: Callable[[CaptionEvent], Awaitable[None]],
                  ctx: "SessionContext") -> None: ...
```

  `SessionContext` expone `session_id`, `source_lang`, `target_lang`, `glossary`, `metrics`.
- Endpoints (docstring en `api/sessions.py` y `api/ws.py`):

| Método | Ruta | Auth | Uso |
|---|---|---|---|
| `GET` | `/healthz` | — | Healthcheck |
| `GET` | `/api/public/sessions` | — | Lista pública: id, título, orador, idiomas, estado |
| `POST` | `/api/sessions` | admin | Crear sala |
| `POST` | `/api/sessions/{id}/start` | admin | Arrancar |
| `POST` | `/api/sessions/{id}/stop` | admin | Parar |
| `DELETE` | `/api/sessions/{id}` | admin | Borrar |
| `GET` | `/api/sessions` | admin | Estado completo + métricas |
| `POST` | `/api/uploads` | admin | Subir mp3 |
| `GET` | `/api/sessions/{id}/export.{srt,vtt,txt,md}?lang=` | — | Exports |
| `GET` | `/api/sessions/{id}/knowledge` | — | Knowledge Pack |
| `POST` | `/api/sessions/{id}/ask` | — (rate limit) | Preguntale a la charla |
| `WS` | `/ws/ingest/{id}?token=` | admin | Audio del mic |
| `WS` | `/ws/captions/{id}?lang=` | — | Subtítulos |
| `WS` | `/ws/admin?token=` | admin | Snapshot de estado cada 1 s |

**Listo cuando:** `events.py` y `engine/base.py` commiteados; tabla de endpoints en el código.

---

## Fase 1 — Base y mínimo viable (H0.75 → H3.5)

### Track A — Motor

#### T1.1 · Fix `FileSource` — A · 25 min · P0

**Funcional:** simular una charla en vivo a velocidad real, sin que el motor la frene, y poder repetirla para pruebas largas.

**Técnico:**
- Pacing sin deriva: en lugar de `sleep(0.1)` fijo, dormir hasta `t_start + n * 0.1` (evita acumular retraso).
- Parámetro `loop: bool`: al terminar el archivo, volver al inicio (necesario para probar la rotación de 10 min con mp3 cortos).
- Productor/consumidor: la sesión corre `source.frames()` en una tarea que llena una `asyncio.Queue(maxsize=50)`; el engine consume de la cola. Si la cola se llena, descartar el frame más viejo y contar `dropped_frames`.
- Actualizar `main_cli.py` para usar este esquema.

**Listo cuando:** un mp3 de 3 min tarda 3:00 ± 2 s en procesarse, aunque el motor sea lento.

#### T1.2 · Actualizar `google-genai` — A · 10 min · P0

**Técnico:**
- `pip install -U google-genai` y fijar la versión exacta en `requirements.txt`.
- Verificar que existen `types.TranslationConfig`, `types.AudioTranscriptionConfig(custom_vocabulary=..., mode=...)` y el campo `interim_input_transcription`:

```bash
python -c "from google.genai import types; print(types.TranslationConfig, types.AudioTranscriptionConfig.model_fields.keys())"
```

**Listo cuando:** versión fijada y el chequeo imprime los campos esperados.

#### T1.3 · `LiveSessionRunner` v0 + CLI — A · 45 min · P0 · depende de T1.1, T1.2

**Funcional:** mantener una conexión Live con Gemini por sala, enviando audio y recibiendo transcripciones.

**Técnico:**
- `engine/live_runner.py`, clase genérica que recibe `model`, `config` y callbacks:
  - `on_input_text(text, is_interim)`, `on_output_text(text)`, `on_audio(pcm24k)`, `on_go_away(time_left)`, `on_error(exc)`.
- Conexión: `async with client.aio.live.connect(model=..., config=...) as s`.
- Tarea emisora: lee frames de la cola y llama `await s.send_realtime_input(audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000"))`. Frames de 100 ms (3.200 bytes).
- Tarea receptora: **envolver en `while True: async for msg in s.receive(): ...`** porque en el SDK `receive()` puede terminar al completarse un turno.
- Despachar:
  - `msg.server_content.input_transcription` / `interim_input_transcription`
  - `msg.server_content.output_transcription`
  - `msg.server_content.model_turn.parts[*].inline_data` (audio)
  - `msg.go_away`
- CLI: `python -m backend.main_cli samples/x.mp3 --engine live_translate --lang en` imprime cada evento con timestamp relativo.

**Listo cuando:** 3 minutos de un mp3 salen por consola con original y traducción (Camino 1) u original (Camino 2).

#### T1.4 · Spike de mediciones — A · 30 min · P0 · depende de T1.3

**Funcional:** decidir con datos, no con supuestos.

**Técnico:** medir y anotar en la tabla del README:
1. **Semántica de los fragmentos:** ¿cada mensaje trae un *delta* (hay que concatenar) o la *hipótesis completa* (hay que reemplazar)? Define cómo se arma el texto.
2. **Cadencia:** cada cuánto llegan mensajes y de qué largo.
3. **Latencia:** tiempo entre que arranca la voz y el primer parcial; entre que termina la frase y el final.
4. **Glosario:** "Kubernetes" y nombres propios con y sin glosario (Camino 2: `custom_vocabulary`; Camino 1: post-proceso).
5. **Camino 2:** `SMART` vs `VERBATIM` (legibilidad y si demora los finales).
6. **Límite de sesión:** dejar corriendo en loop más de 10 min (en segundo plano mientras se hace T1.5): ¿llega `GoAway`? ¿a qué minuto se corta? ¿qué excepción lanza?

**Listo cuando:** las 6 respuestas están en el README.

#### T1.5 · Engine del camino elegido — A · 45 min · P0 · depende de T1.4

**Funcional:** convertir la salida cruda de Gemini en `CaptionEvent` para los dos idiomas.

**Técnico — Camino 1 (`engine/live_translate.py`):**
- Config con `translation_config.target_language_code = "es" if source_lang == "en" else "en"` y `echo_target_language=False`.
- `core/segmenter.py`: un segmentador por track (orig y trans). Acumula fragmentos (según lo aprendido en T1.4) y:
  - emite **interim** con el texto acumulado cada vez que llega un fragmento;
  - emite **final** y abre un `seg` nuevo cuando: termina en `.`, `?`, `!` o `…` y tiene ≥ 20 caracteres; o supera 120 caracteres (corta en el último espacio); o pasan 1,2 s sin fragmentos nuevos.
- Aplicar glosario (T1.7) a cada texto antes de emitir.

**Técnico — Camino 2 (`engine/transcribe_mt.py`):**
- Config con `language_codes=["en-US"]` o `["es-419"]`, `custom_vocabulary=glossary.terms[:100]`, modo según T1.4.
- `interim_input_transcription` → evento interim `kind="orig"` (reemplaza texto del `seg` actual).
- `input_transcription` → aplicar reemplazos del glosario → evento final `kind="orig"` → traducir con Argos (T1.6) vía `await asyncio.to_thread(...)` → evento final `kind="trans"` con el mismo `seg`.

**Listo cuando:** el CLI muestra eventos interim/final coherentes en ambos idiomas durante 3 min.

#### T1.6 · Traductor local Argos (solo Camino 2) — A · 30 min · P0\*

**Funcional:** traducir gratis y sin límite de requests.

**Técnico:**
- `scripts/install_argos.py`: `update_package_index()`, instalar paquetes `en→es` y `es→en`. Se ejecuta en el build del Docker.
- `translate/argos_mt.py`: cargar ambos modelos al arrancar (warmup con una frase) y exponer `translate(text, src, dst) -> str`.
- Protección de términos: reemplazar términos del glosario por marcadores antes de traducir y restaurarlos después. **Probar con 10 frases**: si Argos rompe los marcadores, desactivar el masking y depender solo de los reemplazos post-traducción.
- Medir ms por frase en local (y luego en el Space).

**Listo cuando:** traduce 20 frases de la charla con < 500 ms por frase y los términos del glosario intactos.

#### T1.7 · Módulo de glosario — A · 20 min · P0

**Funcional:** que los términos técnicos y nombres propios salgan bien escritos.

**Técnico:**
- Formato `config/glossary.default.json`:

```json
{
  "terms": ["Nerdearla", "Kubernetes", "Terraform", "Gemini"],
  "replacements": {"cubernetes": "Kubernetes", "nerd earla": "Nerdearla"}
}
```

- Glosario de sesión = default + lo que cargue el operador (se combinan; el de sesión gana).
- `apply(text)`: primero `replacements` (regex, sin distinguir mayúsculas, con límites de palabra); después normalizar mayúsculas de cada `term` (`kubernetes` → `Kubernetes`).
- Parser del textarea de la consola: una línea = un término; `mal => bien` = reemplazo.
- `tests/test_glossary.py` con 5 casos.

**Listo cuando:** tests verdes.

### Track B — Web y deploy

#### T1.8 · Esqueleto FastAPI + config — B · 20 min · P0

**Técnico:**
- `config.py` con `pydantic-settings` leyendo las variables de la tabla.
- `app.py`: crea la app, monta `frontend/` como estáticos en `/`, incluye routers, `GET /healthz` → `{"ok": true, "engine": ENGINE}`.
- `lifespan`: crea el `SessionManager` y, en el shutdown, para todas las sesiones.
- Logging con formato `[sesión] mensaje`.

**Listo cuando:** `make dev` sirve `/healthz` y un `index.html` de prueba.

#### T1.9 · `SessionManager` + `Session` + pub/sub — B · 40 min · P0 · depende de T0.5

**Funcional:** cada sala es independiente; los subtítulos llegan solo a quien mira esa sala y ese idioma.

**Técnico:**
- `Session`: id (slug del título), título, orador, `source_lang`, `target_lang`, tipo de fuente, glosario, estado (`CREATED`, `RUNNING`, `ROTATING`, `RECONNECTING`, `ERROR`, `STOPPED`), `started_at`, métricas.
- `Session.start()` crea una `asyncio.Task` que conecta fuente → cola → engine → `emit`.
- `emit(event)`: guarda finales en un historial en memoria (últimos 50 por idioma), persiste (T2.3) y reenvía a suscriptores.
- Suscriptores: `dict[lang, set[asyncio.Queue]]`, cada cola con `maxsize=100`. Si una cola está llena (cliente lento), descartar el mensaje más viejo; nunca bloquear la sala.
- `SessionManager`: `create`, `get`, `list`, `start`, `stop`, `delete`, `subscribe(id, lang)`, `unsubscribe`.

**Listo cuando:** con un engine falso, dos suscriptores de idiomas distintos reciben solo su idioma.

#### T1.10 · `ReplayEngine` + jsonl de ejemplo — B · 20 min · P0

**Funcional:** simular el motor sin API (para desarrollar el front, para grabar el video y para jurados sin key).

**Técnico:**
- `engine/replay.py`: lee un `captions.jsonl` y reemite cada evento respetando los tiempos originales (diferencias de `t0`).
- `samples/replay_demo.jsonl` inicial: 20 eventos escritos a mano (interim + final, ambos idiomas). Se reemplaza por uno real en T3.11.

**Listo cuando:** `ENGINE=replay` muestra subtítulos en consola al ritmo correcto.

#### T1.11 · WS de captions — B · 20 min · P0 · depende de T1.9

**Técnico:**
- `/ws/captions/{id}?lang=es`: al conectar, enviar el historial de finales de ese idioma y después los eventos en vivo como JSON.
- Si la sala no existe: cerrar con código 4404.
- Mensaje adicional `{"type":"session_status","status":"STOPPED"}` cuando la sala termina (la página de audiencia muestra el link a la página de la charla).
- Uvicorn con `--ws-ping-interval 20 --ws-ping-timeout 20`.

**Listo cuando:** `websocat` (o una página de prueba) recibe historial + eventos del replay.

#### T1.12 · Página de audiencia v0 — B · 40 min · P0 · depende de T1.11

**Funcional:** cada persona elige sala e idioma y lee subtítulos en su celular.

**Técnico (`index.html` + `js/captions.js`):**
- Sin `?s=`: lista de salas desde `/api/public/sessions` (título, orador, estado, botones de idioma).
- Con `?s=ID&lang=es`: vista de subtítulos.
  - Mostrar las últimas 2–3 líneas, alineadas abajo; el texto **interim** en gris itálica se reemplaza cuando llega el **final** del mismo `seg`.
  - Selector de idioma sin recargar (reconecta el WS).
  - Botones A− / A+ para tamaño de letra y modo alto contraste (accesibilidad).
  - Reconexión automática con backoff (1, 2, 4, 8 s, máximo 10 s) e indicador de "reconectando".
- Mobile-first: tipografía grande, sin scroll horizontal.

**Listo cuando:** desde el celular, con `ENGINE=replay`, se ven los subtítulos y se puede cambiar de idioma.

#### T1.13 · Dockerfile HF + primer deploy — B · 40 min · P0

**Funcional:** que cualquiera pueda deployar con "Duplicate this Space".

**Técnico:**
- `Dockerfile`:
  - `FROM python:3.12-slim`; `apt-get install -y ffmpeg`.
  - `useradd -m -u 1000 user` → `USER user` → `WORKDIR /home/user/app` (HF exige usuario no-root UID 1000).
  - `pip install -r requirements.txt`; si Camino 2, `RUN python scripts/install_argos.py` **después** de `USER user` (los modelos quedan en el home del usuario).
  - `COPY --chown=user . .`; `EXPOSE 7860`.
  - `CMD uvicorn backend.app:app --host 0.0.0.0 --port 7860 --ws-ping-interval 20 --ws-ping-timeout 20 --proxy-headers --forwarded-allow-ips="*"`.
- `README.md` con frontmatter YAML al inicio:

```yaml
---
title: Nerdearla Live Captions
emoji: 🎙️
sdk: docker
app_port: 7860
pinned: false
license: mit
---
```

- Crear el Space (Docker, CPU basic, gratis). Secrets: `GEMINI_API_KEY`, `ADMIN_TOKEN`. Variable: `ENGINE`.
- `git remote add hf https://huggingface.co/spaces/<usuario>/<space>` y `make deploy`.
- `DATA_DIR=/home/user/app/data` (disco efímero; está bien para la demo).

**Listo cuando:** `https://<usuario>-<space>.hf.space/healthz` responde y la audiencia con replay funciona desde el celular.

#### T1.14 · Integración checkpoint H3.5 — AB · 15 min · P0

**Técnico:** conectar el engine real de A dentro de `Session`; sala creada por código con un mp3 de `samples/`; deploy.

**Listo cuando:** **mp3 → Space → subtítulos en el celular, en los dos idiomas.** Si no se llega, `ENGINE=chunked` y se sigue.

---

## Fase 2 — Core (H3.5 → H8)

### Track A

#### T2.1 · Rotación + resiliencia del runner — A · 1.5 h · P0 · depende de T1.4

**Funcional:** una charla de 40 min se subtitula sin cortes visibles aunque Gemini cierre la conexión cada ~10 min.

**Técnico:**
- **Rotación preventiva** a los `ROTATE_AFTER_S` (540 s) o al recibir `GoAway` (lo que ocurra primero). Estado de la sala: `ROTATING`.
- **Secuencial:** cerrar la sesión vieja → abrir la nueva (nunca dos abiertas a la vez: no duplica el cupo).
- **Ring buffer:** `collections.deque` con los últimos 2,5 s de frames; al abrir la sesión nueva, reenviarlo primero y después seguir con audio en vivo. Durante la reconexión, los frames nuevos se acumulan en el buffer (se pierde lo que exceda 2,5 s).
- **Dedupe** (`core/dedupe.py`): `dedupe_overlap(prev_tail: str, new: str) -> str`. Toma las últimas ~15 palabras de los finales previos y quita del principio de `new` el prefijo más largo que coincida (normalizando mayúsculas y puntuación). Con tests.
- **Errores:** ante excepción de red o 429, reintentar con backoff exponencial + jitter (1, 2, 4, 8, 16, máximo 30 s). Estado `RECONNECTING`. Después de 10 fallos seguidos: `ERROR` (visible en el panel), la sala no se cae del todo y se puede reintentar desde la consola.
- **Semáforo de proceso** `asyncio.Semaphore(MAX_CONCURRENT_LIVE)`: ninguna sala abre una sesión Live si no hay cupo; queda en `RECONNECTING` hasta que se libere.
- Contadores: `rotations`, `reconnects`, `errors`, `last_error`, `live_sessions_opened_today`.

**Listo cuando:** corrida de 25 min en loop con ≥ 2 rotaciones: sin caídas, sin frases duplicadas visibles y con huecos < 3 s.

#### T2.2 · Aislamiento multi-sala — A · 25 min · P0 · depende de T2.1

**Técnico:**
- Cada `Session.run` envuelto en `try/except` propio; una excepción no controlada pasa esa sala a `ERROR` sin tocar las demás.
- Prueba: 2 salas corriendo; a una se le pasa un archivo corrupto (o se la detiene de golpe) y la otra sigue emitiendo.

**Listo cuando:** la prueba pasa.

#### T2.3 · Persistencia — A · 20 min · P0

**Técnico:**
- `DATA_DIR/sessions/<id>/captions.jsonl`: solo eventos **finales**, una línea por evento, append + flush.
- `meta.json`: título, orador, idiomas, engine, glosario, `started_at`, `stopped_at`, estado del Knowledge Pack, URL de NotebookLM (si existe).
- Al reiniciar el proceso: cargar las sesiones terminadas desde disco (para que sigan visibles sus exports).

**Listo cuando:** después de parar una sala, los archivos existen y se pueden leer.

#### T2.4 · Métricas — A · 50 min · P1

**Funcional:** poder decir "la latencia es X" con números reales y detectar problemas antes que el público.

**Técnico (`core/metrics.py`):**
- **Nivel de audio:** RMS por frame en dBFS.
- **Alerta de silencio:** nivel < −50 dBFS durante más de 20 s → `silence_alert=true`.
- **VAD local simple:** voz = nivel > −45 dBFS (ajustable), con 300 ms de "hangover" para no cortar entre palabras. Registra inicio y fin de cada tramo de voz.
- **Latencia del primer parcial:** tiempo entre inicio de voz y el primer interim siguiente.
- **Latencia del final:** tiempo entre fin de voz y el siguiente final.
- p50 / p95 sobre las últimas 200 muestras (`deque`).
- **Frames:** `last_frame_age_s`, `dropped_frames`.
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
- Validaciones con errores claros (400/404/409).

**Listo cuando:** sin token → 401; con token se crean, arrancan y paran salas desde `curl`.

### Track B

#### T2.6 · WS de ingesta de audio — B · 25 min · P0 · depende de T1.9

**Técnico:**
- `sources/mic_source.py`: `AudioSource` con una `asyncio.Queue(maxsize=50)` (5 s); `push(pcm)` desde el WS; si está llena, descarta el más viejo.
- `/ws/ingest/{id}?token=`: recibe frames binarios de exactamente 3.200 bytes (100 ms de PCM16 LE 16 kHz mono); descarta y cuenta los de otro tamaño.
- Cada 1 s envía al cliente `{"type":"ingest_status","status":"RUNNING","lat_p50_ms":...}` para que la vista de escenario muestre el estado.
- Si no llegan frames durante 3 s: métrica `mic_connected=false`.

**Listo cuando:** un script que manda el mp3 por WS en frames de 100 ms produce subtítulos.

#### T2.7 · Captura de mic con AudioWorklet — B · 1.3 h · P0 · depende de T2.6

**Funcional:** capturar la entrada de la placa de audio desde el browser de la mini PC y mandarla al servidor.

**Técnico (`js/mic.js` + `js/pcm-worklet.js`):**
- Pedir permiso con `getUserMedia({audio: {deviceId, channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false}})` (los filtros de videollamada degradan la señal de una consola).
- **Selector de dispositivo:** `enumerateDevices()` filtrando `audioinput` (las etiquetas solo aparecen después de dar permiso: pedir primero, listar después).
- `AudioContext` a la tasa nativa; el worklet **remuestrea a 16 kHz** con interpolación lineal (funciona en cualquier navegador, sin depender de `AudioContext({sampleRate})`).
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
- Errores de la API visibles (toast).

**Listo cuando:** se crea una sala con mic y otra con mp3, se arrancan y se paran desde la consola.

### Conjuntas

#### T2.10 · Prueba integrada 2 salas × 20 min — AB · 30 min · P0

**Técnico:** en el Space (no en local):
- Sala 1: mic en español (una persona habla o se reproduce el mp3 en ES por parlante).
- Sala 2: mp3 en inglés con loop.
- Checklist: subtítulos en ambos idiomas en ambas salas; ≥ 2 rotaciones por sala sin cortes; celular vía QR; ninguna sala afecta a la otra; métricas coherentes.
- Anotar bugs y resolver los bloqueantes antes de seguir.

**Listo cuando:** checklist completo.

#### T2.11 · Video de emergencia — AB · 30 min · P0

**Técnico:** grabación de pantalla (OBS) de 60–90 s mostrando consola, escenario y celular; subir a YouTube como "no listado".

**Listo cuando:** hay un link de YouTube entregable, aunque sea imperfecto.

---

## Fase 3 — Integración, UX y datos de prueba (H8 → H12.5)

#### T3.1 · Modo overlay — B · 35 min · P1

**Funcional:** subtítulos traducidos quemados en el stream (pain point confirmado por la organización).

**Técnico:**
- Misma `index.html` con `?s=ID&lang=es&overlay=1&bg=transparent|green&size=L&lines=2`.
- Fondo transparente (o verde chroma), sin UI, texto blanco con contorno negro (`text-shadow` en 4 direcciones) para leerse sobre cualquier video, centrado abajo.
- Probar en OBS: Browser Source 1920×1080 con la URL.
- Documentar en el README cómo cargarlo en OBS y en vMix (entrada Web Browser).

**Listo cuando:** en OBS se ven los subtítulos sobre un video de prueba.

#### T3.2 · Panel de monitoreo — B · 1 h · P1 · depende de T2.4

**Funcional:** el equipo ve de un vistazo si alguna sala tiene problemas.

**Técnico:**
- Sección en `admin.html`, alimentada por `/ws/admin` (snapshot cada 1 s).
- Por sala: estado (color), fuente, tiempo activo, nivel de mic + antigüedad del último frame, alerta de silencio, latencia p50/p95 (parcial y final), rotaciones, reconexiones, último error, oyentes por idioma.
- Global: sesiones Live abiertas vs. `MAX_CONCURRENT_LIVE`, sesiones hoy vs. `QUOTA_LIVE_SESSIONS_PER_DAY`, costo acumulado **USD 0**.
- Resaltar en rojo: `ERROR`, silencio, mic desconectado, cuota > 80%.

**Listo cuando:** desenchufar el mic (o parar el envío) se refleja en el panel en < 5 s.

#### T3.3 · Exports — A · 45 min · P1 · depende de T2.3

**Funcional:** al terminar, descargar la transcripción completa en formatos estándar.

**Técnico (`post/exports.py`):**
- Fuente: `captions.jsonl` (finales).
- Armado de cues: máximo 42 caracteres por línea, 2 líneas, 7 s; mínimo 1 s. Los finales largos se parten y el tiempo se reparte proporcional a los caracteres.
- Offset: restar la latencia p50 medida a cada timestamp (para que los subtítulos queden alineados con el audio grabado).
- Formatos: SRT (`00:01:02,500`), VTT (`00:01:02.500`, con cabecera `WEBVTT`), TXT (texto corrido), MD (metadata + transcripción en ambos idiomas con marcas `[mm:ss]`).
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

#### T3.7 · Pasada final de calidad (P2) — A · 30 min

**Técnico:** al hacer Stop, una llamada por idioma a `KP_MODEL` con la transcripción + glosario completo para corregir errores de reconocimiento y traducción, conservando las marcas de tiempo. Si existe, los exports ofrecen "versión revisada" además de la "versión en vivo".

**Listo cuando:** el export revisado corrige al menos los términos del glosario.

#### T3.8 · Audio traducido (P2, solo Camino 1) — A · 1.5 h

**Funcional:** escuchar la traducción con auriculares desde el celular.

**Técnico:**
- El runner ya recibe audio PCM 24 kHz (`on_audio`); reenviarlo a `/ws/audio/{id}?lang=` como frames binarios.
- En la audiencia, botón "🎧 Escuchar" (requiere clic): `AudioContext` a 24 kHz, cola de reproducción con ~300 ms de colchón, cada chunk programado con `source.start(nextTime)`.
- Si el cliente se atrasa más de 2 s, descartar audio viejo y resincronizar.

**Listo cuando:** en el celular se escucha la traducción con retraso estable.

#### T3.9 · Exporter automático a NotebookLM (P2, timebox 1.5 h) — A

**Funcional:** al terminar la charla, se crea sola un notebook con la transcripción y un podcast.

**Técnico (`post/notebooklm.py`, librería no oficial `notebooklm-py`):**
- Local: `pip install notebooklm-py` y `notebooklm login` (abre el navegador y guarda la sesión).
- Script `tools/notebooklm_export.py <session_id>`: crear notebook "Nerdearla 2026 — <título>", agregar la transcripción MD como fuente de texto, generar el Audio Overview y esperar a que termine. **Verificar en el README de la librería** los nombres exactos de los métodos para fuente de texto y para obtener un link compartible.
- Probarlo primero a mano desde local. Si funciona, habilitarlo en el Space: guardar el JSON de sesión como secret `NOTEBOOKLM_STORAGE_JSON`, escribirlo a un archivo al arrancar, y llamar al exporter en el Stop solo si `NOTEBOOKLM_ENABLED=1`.
- Nunca bloquear el Stop: corre en segundo plano y cualquier error solo se loguea.
- **Si a las 1.5 h no funciona, se abandona** (las capas 1 y 3 ya cubren la idea).

**Listo cuando:** al parar una sala, `meta.json` tiene `notebooklm_url` y el link funciona.

#### T3.10 · `docker-compose.yml` + túnel opcional — A · 20 min · P1

**Técnico:**
- Servicio `app`: `build: .`, `ports: ["7860:7860"]`, `env_file: .env`, volumen `./data:/home/user/app/data`.
- Servicio `tunnel` bajo el perfil `tunnel`: imagen `cloudflare/cloudflared`, comando `tunnel --url http://app:7860` (URL HTTPS pública gratis, para correr en la mini PC sin nube).
- Uso documentado: `docker compose up` y `docker compose --profile tunnel up`.

**Listo cuando:** en una máquina limpia, `docker compose up` levanta la app en `localhost:7860`.

#### T3.11 · Samples, glosario default, replay real — AB · 20 min · P0

**Técnico:**
- Recortar los 2 mp3 a 2–3 min (mantenerlos chicos para el repo y para HF):
  `ffmpeg -i original.mp3 -ss 00:05:00 -t 180 -ac 1 -b:a 64k samples/en_talk_3min.mp3`
- Nombres claros: `samples/en_talk_3min.mp3`, `samples/es_talk_3min.mp3`.
- `config/glossary.default.json` con términos de las charlas de prueba + Nerdearla.
- Reemplazar `samples/replay_demo.jsonl` por el `captions.jsonl` de una corrida real buena.

**Listo cuando:** los tres elementos están commiteados y el replay usa datos reales.

#### T3.12 · README completo — B · 1 h · P0 (A revisa)

**Secciones:**
1. Qué es (2 párrafos) + GIF o captura.
2. Probalo en 3 minutos: Duplicate this Space → secrets → `/admin.html` → sala con sample → abrir audiencia.
3. Arquitectura (diagrama de `PLAN.md` §2.4) y decisión de caminos.
4. Cómo crear la API key **sin billing** y cómo chequear cuotas en AI Studio.
5. Variables de entorno (tabla).
6. Operación en un evento: mic por placa de audio en Chrome, vista de escenario, QR, overlay en OBS/vMix, panel.
7. Después de la charla: exports, Knowledge Pack, NotebookLM.
8. Self-host: `docker compose` y túnel.
9. Cómo escalar: Spaces por grupo de salas, key por sala, límites del free tier, modo local (roadmap).
10. Métricas medidas (tabla de T1.4 + latencias de T2.10).
11. Privacidad: en free tier Google usa el contenido para mejorar sus productos.
12. Licencia MIT y créditos.

**Listo cuando:** alguien que no conoce el proyecto puede deployarlo solo con el README (se valida en T4.1).

---

## Fase 4 — Testing, freeze y pitch (H12.5 → H15)

#### T4.1 · E2E desde cero — AB · 30 min · P0

**Técnico:** simular otra conferencia: con otra cuenta de HF (o un Space nuevo), seguir **solo el README**: duplicar, cargar secrets, crear 2 salas, ver subtítulos en el celular, parar, ver el resumen. Corregir cada hueco de documentación encontrado.

**Listo cuando:** el flujo completo sale sin preguntarle nada al equipo.

#### T4.2 · Hardening y caminos de error — AB · 25 min · P0

**Técnico:** verificar que cada error tenga un mensaje claro:
- API key inválida → sala en `ERROR` con mensaje legible en el panel.
- Permiso de mic denegado → aviso en la vista de escenario.
- Archivo que no es audio → 400 en la consola.
- Sala inexistente en la audiencia → mensaje "Sala no encontrada".
- Repetir la prueba de 2 salas × 20 min después del último merge.

**Listo cuando:** todos los casos probados.

#### T4.3 · Code freeze + tag — AB · 5 min · P0

**Técnico:** a las **H13.5**, `git tag v1.0.0` y push a GitHub y HF. Desde acá solo bugfixes.

#### T4.4 · Video final — AB · 1 h · P0

**Técnico:**
- Guion (1–2 min): ver `PLAN.md` §5. Usar audio de una charla de Nerdearla.
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

## Orden de recorte si falta tiempo

1. T3.8 audio traducido y T3.9 NotebookLM automático.
2. T3.7 pasada final.
3. Quiz dentro de T3.4/T3.5 (quedan resumen + preguntas).
4. T3.2 panel → tabla simple con `GET /api/sessions` refrescada cada 2 s.

**Nunca se recorta:** T2.7 mic, T2.10 dos salas, EN↔ES, T1.12 audiencia, T3.12 README, T1.13 deploy, T4.4 video, T4.5 envío.
