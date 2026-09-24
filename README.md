---
title: Nerdearla Live Captions
emoji: 🎙️
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Nerdearla Live Captions

Subtítulos y traducción EN ↔ ES en vivo para conferencias, con Gemini Live (free tier, costo cero). Una sala = una sesión Live que devuelve el original y la traducción; la audiencia elige sala e idioma desde el celular.

Estado: **Fase 1** — motor Camino 1 (`live_translate`), sesiones con pub/sub por idioma, WS de subtítulos, página de audiencia, modo replay y Dockerfile para HF Spaces. Plan y backlog: [`backend/docs/PLAN.md`](backend/docs/PLAN.md) · [`backend/docs/TASKS.md`](backend/docs/TASKS.md).

## Correr en local

**Con Docker** (no hace falta Python ni ffmpeg en el host):

```bash
cp .env.example .env            # GEMINI_API_KEY de un proyecto SIN billing
make docker-test                # tests
make docker-run                 # http://localhost:7860  (ENV_FILE=otra/ruta/.env para usar otro archivo)
```

**Con Python 3.12 + ffmpeg:**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
make dev                        # http://localhost:7860
make test
```

Sin API key: `ENGINE=replay` crea una sala "Demo" que reproduce [`samples/replay_demo.jsonl`](samples/replay_demo.jsonl) en loop. Con key: `DEMO_FILE=samples/en_talk_3min.mp3` crea y arranca una sala con ese archivo (hasta que exista la consola de operador, T2.9).

## CLI

```bash
python -m backend.main_cli samples/en_talk_3min.mp3 --lang en                 # EN -> ES
python -m backend.main_cli samples/es_talk_2min.mp3 --lang es                 # ES -> EN
python -m backend.main_cli samples/replay_demo.jsonl --engine replay          # sin API
python -m scripts.spike_live samples/en_talk_3min.mp3 --lang en               # mediciones T1.4
python -m scripts.spike_live samples/en_talk_3min.mp3 --lang en --loop --minutes 12
python -m scripts.live_probe --sessions 2 --trials 3                           # T2.10a: concurrencia, SDK crudo
python -m scripts.runner_probe samples/mp3/a.mp3:en samples/es_talk_2min.mp3:es  # T2.10a: con nuestro engine
```

En Docker: `docker run --rm --env-file .env nerdearla-captions python -m backend.main_cli samples/en_talk_3min.mp3 --lang en`.

## Deploy en Hugging Face Spaces

1. Crear un Space: SDK **Docker**, hardware **CPU basic** (gratis).
2. Settings → **Secrets**: `GEMINI_API_KEY`, `ADMIN_TOKEN`. **Variables**: `ENGINE` y, para el checkpoint, `DEMO_FILE=samples/en_talk_3min.mp3`.
3. `pip install -U huggingface_hub` y `hf auth login`.
4. `make deploy HF_SPACE=<usuario>/<space>`.
5. Abrir `https://<usuario>-<space>.hf.space/healthz`.

`make deploy` sube el árbol de trabajo con `hf upload` (sin historial git: HF rechaza pushes con binarios fuera de Xet/LFS y el historial tiene los PNG de `backend/docs/diagrams`). Excluye `.env`, `data/` y `samples/mp3/`.

## Variables de entorno

| Variable | Default | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | — | Key de un proyecto **sin billing** |
| `ENGINE` | `live_translate` | `live_translate` (Camino 1) · `chunked` (fallback A) · `replay` · `transcribe_mt` (Camino 2, no implementado) |
| `ADMIN_TOKEN` | — | Protege consola, API admin e ingesta de audio (T2.5) |
| `DATA_DIR` | `./data` | Sesiones, uploads, cuota |
| `LIVE_TRANSLATE_MODEL` | `gemini-3.5-live-translate-preview` | Camino 1 |
| `TRANSCRIBE_MODEL` | `gemini-3.5-transcribe-live` | Camino 2 |
| `KP_MODEL` | `gemini-3.1-flash-lite` | Knowledge Pack, ask, pasada final |
| `MAX_CONCURRENT_LIVE` | `2` | Tope de sesiones Live abiertas en el proceso |
| `ROTATE_AFTER_S` | `540` | Rotación preventiva (9 min) |
| `QUOTA_LIVE_SESSIONS_PER_DAY` | `0` | Cupo diario (0 = no mostrar) |
| `NOTEBOOKLM_ENABLED` | `0` | Exporter no oficial (P2) |
| `LOG_LEVEL` | `INFO` | |
| `SEGMENT_IDLE_S` | `2.0` | Segundos sin fragmentos que cierran un segmento (provisorio, ver Mediciones) |
| `GEMINI_MODEL` · `CHUNK_SECONDS` · `OVERLAP_SECONDS` | `gemini-2.5-flash` · `5` · `0.75` | Fallback A (`ENGINE=chunked`) |
| `REALTIME` | `1` | `0` = leer los archivos sin pacing de tiempo real |
| `REPLAY_FILE` | `samples/replay_demo.jsonl` | Eventos que reproduce `ENGINE=replay` |
| `DEMO_FILE` | — | Audio de la sala "Demo" que se crea al arrancar (motores con API) |
| `DEMO_LANG` | `en` | Idioma de la charla de `DEMO_FILE` |
| `DEMO_LOOP` | `0` | `1` = repetir `DEMO_FILE` (gasta cuota sin parar) |

## Mediciones (T1.4)

Medido el 24/9/2026 con `gemini-3.5-live-translate-preview`: `samples/en_talk_3min.mp3` (EN → ES, 3 min y 10 min en loop) y `samples/es_talk_2min.mp3` (ES → EN). Herramienta: `scripts/spike_live.py` (log crudo en `data/spike/`, no se commitea). Las latencias usan un VAD por energía (−45 dBFS), así que son aproximadas.

| # | Pregunta | Resultado |
|---|---|---|
| 1 | Semántica de los fragmentos | **Delta**: cada mensaje trae solo el texto nuevo, con espacio inicial, y hay que concatenarlo (el segmentador ya lo hace). No llega `interim_input_transcription` y `finished` nunca vale `True`: los finales los arma el segmentador. |
| 2 | Cadencia y largo | ~1 mensaje/s por track (p50 1,0 s), ~13 caracteres (máx. 35). Además llegan audio traducido continuo (4 chunks/s, a tiempo real), `usage_metadata` y `session_resumption_update` (~1/s). |
| 3 | Latencia | Voz → primer fragmento del original: p50 0,5–0,6 s. Fin de voz → siguiente fragmento: p50 0,45–0,55 s. Traducción ES → EN: p50 0,6 s, sin huecos de más de 2 s. **Traducción EN → ES: arranca 0,2–0,5 s detrás del original, pero en la corrida de 10 min (casi siempre con otra sesión en paralelo, ver abajo) tuvo frenazos de 12 a 55 s seguidos de ráfagas y a los 10 min cubría el 84 % del texto. Sola, la corrida de 3 min terminó de traducir ~20 s después del final del audio.** Al final de cada segmento se suma el segmentador (puntuación o `SEGMENT_IDLE_S` sin fragmentos). |
| 4 | Glosario | Bien escritos: Unix, Windows, Emacs, Wayland, Go, Bell Labs, MIPS, Pentium, Greenfield. Mal: "UTF-8" → "UTF", "TCP/IP" → "TCP IP", "Brownfield" → "groundfield" (y una vez "Greenfield"). El Camino 1 no acepta vocabulario: el post-proceso corrige errores consistentes (`groundfield => Brownfield`, `TCP IP => TCP/IP`), pero no palabras que el modelo omite ni confusiones con otro término válido. |
| 5 | `SMART` vs `VERBATIM` | N/A (solo Camino 2) |
| 6 | Límite de sesión | La **conexión** dura ~10 min: `GoAway` a los **540,6 s (9:00)** con `time_left=50s`; si el cliente no cierra, el servidor corta a los **590,7 s** con `ConnectionClosedError 1008 (policy violation)`. La **sesión** solo de audio dura 15 min sin compresión (docs), y se puede **reanudar** en otra conexión con el handle de `session_resumption_update` (llegan ~1/s con `resumable: true`, válidos 2 h). Probado: reconexión con el handle en 1,3 s y el texto sigue sin repetir. La rotación de T2.1 se basa en eso. |

Otro dato: al terminar el audio, el modelo sigue mandando audio traducido ~15 s más; por eso el runner espera hasta 30 s antes de cerrar (`drain_max_s`).

**Concurrencia (probe T2.10a, `scripts/live_probe.py`: SDK crudo, un proceso, sin backend, 40 s por sesión):**

| Prueba | Resultado |
|---|---|
| 1 sesión, justo después de otras corridas (17:48, 17:51) | degradada: primer texto a 7 s y 13,5 s; 10 y 3 fragmentos (normal: ~36) |
| 1 sesión, tras ~3 min sin uso | normal: 36 fragmentos, primer texto a 4,5 s |
| 2 simultáneas × 3, enseguida de la anterior | en las 3, una normal (36) y la otra degradada (5–13 fragmentos, primer texto a 6–12 s) |
| 2 escalonadas 10 s, enseguida | la primera degradada **aun estando sola** los primeros 10 s; la segunda normal |
| **2 simultáneas tras 5 min sin uso** | **las dos normales** (36/36, primer texto a 4,1 y 5,1 s) |
| **Reanudación** (cerrar a mitad y reconectar con el handle) | **reconexión en 1,3 s, el texto sigue sin repetir ni perder contexto** |
| 1 sesión nueva enseguida de la reanudación | normal (36) |
| **2 salas con nuestro runner/engine** (`scripts/runner_probe.py`, EN + ES, un proceso, en frío) | **las dos normales**: primer texto a 4,1 y 3,3 s, ~8 msgs/s, 0 frames perdidos, callbacks ≤ 1,4 ms |

Lectura: el proyecto **sí sostiene 2 sesiones simultáneas**; lo que degrada a una de ellas es abrir sesiones nuevas cuando ya hubo varias en los minutos previos (¿cupo retenido por sesiones recién cerradas o límite de arranques?; el efecto se va en < 5 min). Consecuencias: rotar **reanudando** (T2.1), no abrir sesiones nuevas de más (el `SessionManager` rechaza el Start de una sala más allá de `MAX_CONCURRENT_LIVE`), y vigilar `runner.stats` para detectar una sesión que conecta pero responde lento. Falta confirmar el cupo en AI Studio → Rate limits.

**Segmentador:** el corte por silencio pasó de 1,2 s a **2,0 s** (`SEGMENT_IDLE_S`, provisorio). Reproduciendo sin red los fragmentos reales del spike EN (cadencia normal), los cortes por silencio bajan de 4 a 1 en el original y de 10 a 8 en la traducción, con la misma cantidad de finales (34 y ~25). Los finales cortos que quedan en la traducción ("Este," o "para") vienen de sus frenazos de más de 2 s: ningún corte fijo los evita.

## Muestras

| Archivo | Contenido |
|---|---|
| `samples/en_talk_3min.mp3` | "Interview with Rob Pike", 0:30–3:30 (EN) |
| `samples/es_talk_2min.mp3` | "Brownfield engineering", Nicolás Páez, completo (2:10) |
| `samples/replay_demo.jsonl` | 20 eventos escritos a mano (interim + final, EN y ES) |

Los originales van en `samples/mp3/` (ignorado por git).

## Privacidad

En el free tier, Google usa el contenido enviado para mejorar sus productos. Para charlas públicas es aceptable, pero hay que saberlo.

## Licencia

MIT
