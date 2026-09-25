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

**Estado: Fase 2 (Core) en curso.**
- **Funciona:** motor Camino 1 (`live_translate`), salas con pub/sub por idioma, WS de subtítulos, página de audiencia, modo replay, límite de salas Live (`MAX_CONCURRENT_LIVE`, 409 al pasarlo), persistencia asíncrona y el Dockerfile para HF Spaces.
- **Falta:** rotación de la sesión Live (hoy una sala no pasa de ~10 min), API de administración, captura de mic y consola de operador. Ver el [roadmap](docs/ROADMAP.md#2-estado-actual).

## Documentación

| Documento | Qué responde |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Cómo está hecho y por qué: arquitectura actual y objetivo (con diagramas), comportamiento medido de Gemini Live, despliegue, escalabilidad y decisiones |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Qué falta y en qué orden: estado actual, tablero, roadmap de escalabilidad, backlog de tareas, entrega y riesgos |
| [`docs/CONCURRENCY-REPORT.md`](docs/CONCURRENCY-REPORT.md) | Cuántas salas soportamos: lo documentado por Google, lo observado (con branch + commit + fecha), el límite operativo y el veredicto. Fuente de verdad sobre capacidad |
| [`docs/alternatives/`](docs/alternatives/) | Opciones evaluadas y no implementadas: [motores de transcripción](docs/alternatives/TRANSCRIPTION-ENGINES.md) y [edge / hostings](docs/alternatives/CLOUD-EDGE.md) |

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

Sin API key: `ENGINE=replay` crea una sala "Demo" (o `DEMO_ROOMS` salas) que reproduce [`samples/replay_demo.jsonl`](samples/replay_demo.jsonl) en loop. Con key: `DEMO_FILE=samples/en_talk_3min.mp3` crea y arranca una sala con ese archivo (hasta que exista la consola de operador, T2.9).

## CLI

```bash
python -m backend.main_cli samples/en_talk_3min.mp3 --lang en                 # EN -> ES
python -m backend.main_cli samples/es_talk_2min.mp3 --lang es                 # ES -> EN
python -m backend.main_cli samples/replay_demo.jsonl --engine replay          # sin API
python -m scripts.spike_live samples/en_talk_3min.mp3 --lang en               # mediciones T1.4
python -m scripts.spike_live samples/en_talk_3min.mp3 --lang en --loop --minutes 12
python -m scripts.live_probe --sessions 2 --trials 3                           # concurrencia, SDK crudo
python -m scripts.runner_probe samples/en_talk_3min.mp3:en samples/es_talk_2min.mp3:es \
    --trials 3 --cooldown 300 --layer engine                                   # concurrencia, con nuestro engine (o --layer session)
python -m scripts.probe_metrics data/probe/runner-*.json --baseline <reporte N=1>  # tabla clasificada
python -m scripts.audience_load --clients 10,50,100 --seconds 60               # fan-out contra ENGINE=replay, sin Gemini
```

En Docker: `docker run --rm --env-file .env nerdearla-captions python -m backend.main_cli samples/en_talk_3min.mp3 --lang en`.

## Deploy en Hugging Face Spaces

1. Crear un Space: SDK **Docker**, hardware **CPU basic** (gratis).
2. Settings → **Secrets**: `GEMINI_API_KEY`, `ADMIN_TOKEN`. **Variables**: `ENGINE` y, para el checkpoint, `DEMO_FILE=samples/en_talk_3min.mp3`.
3. `pip install -U huggingface_hub` y `hf auth login`.
4. `make deploy HF_SPACE=<usuario>/<space>`.
5. Abrir `https://<usuario>-<space>.hf.space/healthz`.

`make deploy` sube el árbol de trabajo con `hf upload`, sin historial git: HF rechaza pushes con binarios fuera de Xet/LFS, y el historial todavía tiene PNG de diagramas que ya no se usan. Excluye `.env`, `data/` y `samples/mp3/`.

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
| `MAX_CONCURRENT_LIVE` | `2` | Límite **operativo** del backend (no de Gemini): salas con sesión Live a la vez; la siguiente recibe `CapacityError` / 409. Ver [reporte de concurrencia](docs/CONCURRENCY-REPORT.md) |
| `ROTATE_AFTER_S` | `540` | Rotación preventiva (9 min) |
| `QUOTA_LIVE_SESSIONS_PER_DAY` | `0` | Cupo diario (0 = no mostrar) |
| `NOTEBOOKLM_ENABLED` | `0` | Exporter no oficial (P2) |
| `LOG_LEVEL` | `INFO` | |
| `SEGMENT_IDLE_S` | `2.0` | Segundos sin fragmentos que cierran un segmento (provisorio, ver [arquitectura §3](docs/ARCHITECTURE.md#3-comportamiento-medido-de-gemini-live)) |
| `GEMINI_MODEL` · `CHUNK_SECONDS` · `OVERLAP_SECONDS` | `gemini-2.5-flash` · `5` · `0.75` | Fallback A (`ENGINE=chunked`) |
| `REALTIME` | `1` | `0` = leer los archivos sin pacing de tiempo real |
| `REPLAY_FILE` | `samples/replay_demo.jsonl` | Eventos que reproduce `ENGINE=replay` |
| `DEMO_FILE` | — | Audio de la sala "Demo" que se crea al arrancar (motores con API) |
| `DEMO_LANG` | `en` | Idioma de la charla de `DEMO_FILE` |
| `DEMO_LOOP` | `0` | `1` = repetir `DEMO_FILE` (gasta cuota sin parar) |
| `DEMO_ROOMS` | `1` | Con `ENGINE=replay`: cantidad de salas demo (prueba de audiencia) |

## Mediciones

Medido el 24 y 25/9/2026 con `gemini-3.5-live-translate-preview` y los samples de abajo. Detalle y método en [`docs/ARCHITECTURE.md` §3](docs/ARCHITECTURE.md#3-comportamiento-medido-de-gemini-live) y [`docs/CONCURRENCY-REPORT.md`](docs/CONCURRENCY-REPORT.md).

| Qué | Resultado |
|---|---|
| Latencia del original | Voz → primer fragmento: p50 0,5–0,6 s |
| Traducción | ES → EN: p50 0,6 s. EN → ES: arranca 0,2–0,5 s detrás del original, pero tiene frenazos de más de 10 s |
| Límite de conexión | `GoAway` a los 9:00; corte a los 9:50 (`1008`). Se reanuda con el handle en ~1,3 s sin repetir texto (base de la rotación, T2.1) |
| Concurrencia | *2 sesiones concurrentes son una capacidad operativa observada, todavía no garantizada.* Con 3, ninguna conectó en 2 de 3 intentos. Veredicto pendiente |

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
