# Plan de ejecución — Transcripción simultánea en vivo (Nerdearla Vibeathon 2026\)

> Documento de trabajo del equipo. Consolida la arquitectura, el roadmap y los riesgos. Reemplaza las decisiones de `referencia-proyecto.md` donde haya conflicto (ver sección 0).

---

## Restricciones confirmadas

| Tema | Decisión |
| :---- | :---- |
| Equipo | 2 personas — **A** \= motor/Python, **B** \= web/deploy |
| Tiempo | 15 h de reloj en paralelo. El MVP cierra en H8 (si fueran 7,5 h por persona, igual llega) |
| Deadline | Devpost antes del **25/9 15:00 UTC** (12:00 ART), con 1 h de margen |
| Costo | **Cero, 100%.** Solo free tier de Gemini, sin créditos |
| Duración de charlas | \~40 minutos |
| Idiomas | EN → ES y ES → EN (los dos) |
| Español de salida | El más fácil: neutro (`es`, default de los modelos) |
| Despliegue | Hosteado, gratis, sencillo de replicar en cualquier conferencia, idealmente escalable |
| Audio de prueba | 2 archivos mp3 propios |
| Frontend | El más rápido y gratis: HTML \+ JS vanilla, sin build |
| NotebookLM | Sencillo e idealmente automatizado |

---

## 0\. Hallazgos que cambian el plan original

### Google ya tiene modelos de streaming hechos para esto

- **`gemini-3.5-transcribe-live`** — STT en streaming con transcripciones *interim* (parciales, mientras la persona habla) y *finales* (en las pausas). Acepta `custom_vocabulary` de hasta 1.000 términos (rinde mejor con \~100): es el glosario, pero nativo. Modo `SMART` limpia muletillas. **Límite: 10 minutos por sesión** → hay que rotar.  
- **`gemini-3.5-live-translate-preview`** — traducción speech-to-speech en tiempo real, 70+ idiomas, stream continuo. Devuelve transcripción del original **y** de la traducción en la misma sesión. No acepta instrucciones → sin glosario en el prompt.

### El enfoque de chunks del paso 1 no entra en el free tier

- Una charla de 40 min en chunks de 5 s son **\~480 requests**.  
- Google no publica los límites del free tier (hay que mirarlos en AI Studio), pero snapshots de terceros reportan valores muy bajos para modelos de texto: Gemini 3.5 Flash ≈ 5 RPM / 20 RPD; 3.1 Flash-Lite ≈ 15 RPM / 500 RPD. **Verificar con la key real.**  
- Además tiene un piso de latencia estructural (esperar a que el chunk se llene \+ request): \~4–8 s.  
- **No se tira nada:** `AudioSource`, `FileSource`, `normalize` y el CLI se reusan. Cambia el motor; el engine de chunks queda como fallback.

### Bugs del paso 1 a arreglar ya (distorsionan las métricas)

1. `main_cli` consume el `FileSource` en el mismo loop que hace `await` a Gemini: mientras dura cada request, el "audio en vivo" se pausa. La charla se estira y el `e2e` medido es solo la latencia del request. **Fix:** productor (fuente → `asyncio.Queue`) y consumidor en tareas separadas.  
2. `gemini-2.5-flash` razona (thinking) por defecto → latencia extra.  
3. Overlap de 0,75 s sin deduplicación → palabras repetidas en los bordes.  
4. El prompt pide "Rioplatense, neutral tone" (contradictorio). Decisión: español neutro.

### Tres avisos de costo cero

1. **La API key tiene que salir de un proyecto SIN billing.** Vincular billing sube el proyecto a Tier 1 automáticamente y desde ahí se cobra. Crear un proyecto nuevo en AI Studio solo para esto.  
2. **Los límites son por proyecto, no por API key.** Crear más keys en el mismo proyecto no suma cuota.  
3. **En el free tier, Google usa el contenido para mejorar sus productos.** Para charlas públicas es aceptable, pero tiene que estar en el README.

---

## 1\. Diagnóstico y propuesta de valor

**Problema clave:** las conferencias open source no pueden ofrecer subtítulos y traducción en vivo a escala, porque las soluciones actuales son comerciales, caras, manuales y no replicables. Nerdearla lo siente este año con 30+ charlas en inglés, muchas en simultáneo.

**Diferenciador / efecto wow:** el motor de transcripción ya es commodity (Google publicó ejemplos oficiales de traducción en vivo para eventos). Lo que nos diferencia es:

- **Capa de operación de evento:** subtítulos en \~1–2 s con glosario por charla, en tres superficies (pantalla del escenario, celular vía QR, overlay para OBS/vMix) y un panel de monitoreo.  
- **Costo cero operativo:** la única dependencia en la nube que corre segundo a segundo es **una sesión de audio Live por sala**. Todo lo demás corre gratis en el mismo container; las llamadas a modelos de texto se reducen a 1–2 por charla.  
- **Después de la charla:** al hacer *stop*, la charla se convierte sola en un **Knowledge Pack** (resumen, puntos clave, quiz, "Preguntale a la charla") y opcionalmente en un notebook de NotebookLM con podcast.

**Pitch:** *"Duplicás el Space, pegás una API key gratis, y tenés N escenarios subtitulados en dos idiomas."*

---

## 2\. Arquitectura

### 2.1 Alternativas evaluadas

|  | A. Chunks REST (paso 1\) | B. Streaming Live (elegida) | C. 100% local (Whisper \+ Gemma) |
| :---- | :---- | :---- | :---- |
| Latencia | \~4–8 s | parciales en \~1 s (a medir) | depende del hardware |
| Glosario | en el prompt | `custom_vocabulary` nativo o post-proceso | en el prompt |
| Cuota free tier | \~480 req/charla → no entra | \~5 sesiones/charla | sin cuota |
| Esfuerzo desde hoy | ya hecho | \~3 h | alto |
| Riesgo | bajo | límite de 10 min, cupo de sesiones | hardware, calidad del español |

**Decisión:** B como motor principal. A queda como fallback detrás del flag `ENGINE=`. C va al roadmap del README.

### 2.2 Presupuesto de requests por charla de 40 min

| Enfoque | Uso de API por charla | ¿Entra en free tier? |
| :---- | :---- | :---- |
| Chunks de 5 s (paso 1 actual) | \~480 requests | No |
| transcribe-live \+ traducción por API frase a frase | \~5 sesiones \+ 400–800 requests | No |
| **Camino 1:** live-translate | \~5 sesiones (rotación c/ \~9 min) \+ 1–2 al final | Sí, si alcanza el cupo de sesiones |
| **Camino 2:** transcribe-live \+ traducción local | \~5 sesiones \+ 1–2 al final | Sí |

### 2.3 Decisión en H0 (primeros 30 min)

Entrar en **AI Studio → Rate limits** y anotar sesiones concurrentes, RPM y RPD de:

- `gemini-3.5-live-translate-preview`  
- `gemini-3.5-transcribe-live`  
- `gemini-3.1-flash-lite`  
- Gemma 4

| Resultado del chequeo | Camino |
| :---- | :---- |
| live-translate permite ≥ 2 sesiones concurrentes y suficientes sesiones diarias | **Camino 1** |
| live-translate no alcanza, pero transcribe-live sí | **Camino 2** |
| Ningún modelo Live entra en free tier | Modo degradado (Whisper en CPU) — replantear |

**Camino 1 — live-translate (el más simple):**

- Una sesión por sala entrega original \+ traducción.  
- El idioma de la sala define el destino: charla en EN → `es`, charla en ES → `en`.  
- `input_transcription` \= original, `output_transcription` \= traducción.  
- Glosario como post-proceso de reemplazo (el modelo no acepta instrucciones).  
- Trae el **audio traducido** de regalo (feature opcional).

config \= types.LiveConnectConfig(

    response\_modalities=\["AUDIO"\],

    input\_audio\_transcription=types.AudioTranscriptionConfig(),   \# original

    output\_audio\_transcription=types.AudioTranscriptionConfig(),  \# traducción

    translation\_config=types.TranslationConfig(

        target\_language\_code="es" if sala.idioma \== "en" else "en",

        echo\_target\_language=False,

    ),

)

**Camino 2 — transcribe-live \+ traducción local:**

- Transcripción con `custom_vocabulary` (glosario nativo) y modo `SMART`.  
- Traducción **local en CPU** con Argos Translate (MIT, modelos OPUS), protegiendo los términos del glosario con placeholders.  
- Cero requests y sin límite. Menos calidad que un LLM: validar con los mp3.

config \= types.LiveConnectConfig(

    response\_modalities=\["TEXT"\],

    input\_audio\_transcription=types.AudioTranscriptionConfig(

        language\_codes=\["en-US"\],           \# o \["es-419"\] según la sala

        custom\_vocabulary=glossary\[:100\],   \# ≤100 términos rinde mejor

        mode="SMART",                       \# comparar contra VERBATIM

    ),

)

\# interim\_input\_transcription \-\> caption interim (gris, se reemplaza)

\# input\_transcription         \-\> caption final

**En ambos caminos:** al hacer *stop*, una sola pasada con Flash-Lite y el glosario completo pule la transcripción y la traducción finales, que alimentan los exports y el Knowledge Pack.

### 2.4 Flujo de datos

Mini PC (browser, HTTPS)                 HF Space (Docker gratis: 2 vCPU / 16 GB)

┌─────────────────────┐   WS audio PCM   ┌──────────────────────────────────────────────┐

│ Vista escenario:    │ ───────────────► │ Stage worker (1 asyncio.Task por sala)       │

│ captura placa audio │                  │  ├─ LiveSessionRunner ◄─WS─► Gemini Live     │

│ \+ subtítulos \+ QR   │ ◄── captions ─── │  │   (rotación c/\~9 min, ring buffer 2 s)    │

└─────────────────────┘                  │  ├─ Glosario (post-proceso o custom\_vocab)   │

 FileSource (mp3) ─────────────────────► │  ├─ Traductor local Argos (solo Camino 2\)    │

                                         │  └─ captions.jsonl                           │

Celulares (QR) / Overlay OBS ◄── WS ──── │ SessionManager: pub/sub sala+idioma, métricas│

Panel de monitoreo ◄── WS ────────────── │ Al stop: 1–2 llamadas → Knowledge Pack,      │

                                         │   SRT/VTT, (opcional) NotebookLM             │

                                         └──────────────────────────────────────────────┘

Cada sala corre su tubería completa, aislada: si una falla, no afecta al resto. Todas comparten el event loop, así que nada en el camino Gemini → segmentador → broadcast puede bloquear: la escritura de `captions.jsonl` va por una cola y un thread (`core/persistence.py`).

### 2.5 Contratos (congelar en H0)

**Evento de caption** (todo pasa por este JSON):

{"session":"sala-1","lang":"es","seg":42,"final":true,"text":"...","t0":812.4,"t1":815.9,"lat\_ms":1340}

**Endpoints:**

| Método | Ruta | Uso |
| :---- | :---- | :---- |
| `POST` | `/api/sessions` | Crear sala (nombre, idioma, fuente, glosario) |
| `POST` | `/api/sessions/{id}/start` · `/stop` | Arrancar / parar |
| `GET` | `/api/sessions` | Estado de todas las salas (alimenta el panel) |
| `WS` | `/ws/ingest/{id}` | Audio del mic (PCM16 16 kHz, frames de 100 ms) |
| `WS` | `/ws/captions/{id}?lang=` | Subtítulos para audiencia / overlay |

Cada cliente de audiencia tiene una cola acotada: si un celular es lento, se descartan mensajes viejos en vez de frenar la sala.

### 2.6 Rotación de sesión (pieza más riesgosa)

Hay que distinguir dos límites (docs de *session management* + medición de T1.4):

- **Conexión (WebSocket): \~10 min.** Medido: `GoAway` a los 9:00 con `time_left=50s`; si el cliente no cierra, corte a los 9:50 con `1008`.  
- **Sesión solo de audio: 15 min sin compresión**, extensible con `context_window_compression` (ventana deslizante). Para charlas de 40 min hay que activarla (verificar que live-translate la acepte).

Cómo se rota:

- **Reanudar, no empezar de cero:** pedir `session_resumption` y guardar el último handle de `session_resumption_update` (válido 2 h; en T1.4 llegan \~1/s con `resumable: true`). Ante `GoAway` o a los \~9 min, reconectar pasando ese handle: el modelo conserva el contexto.  
- **Audio durante la reconexión:** se acumula en un buffer y se manda apenas conecta; `last_consumed_client_message_index` dice qué audio ya consumió el servidor, para reenviar solo el resto (sin duplicar texto). Solo viene con `SessionResumptionConfig(transparent=True)`: sin eso llegó vacío en el probe.  
- **Fallback si la reanudación falla:** sesión nueva + ring buffer de \~2,5 s + dedupe del primer final.  
- Siempre **secuencial** (cerrar → reconectar): nunca dos conexiones de la misma sala a la vez.  
- Backoff exponencial ante errores o 429, sin tumbar la sala.

### 2.7 Stack

- **Frontend / UX:**  
  - HTML \+ JS vanilla sin build step, servido por FastAPI.  
  - Captura con AudioWorklet → PCM16 16 kHz en frames de 100 ms.  
  - `getUserMedia` con `echoCancellation`, `noiseSuppression` y `autoGainControl` en `false` (la señal viene de una consola; esos filtros la degradan).  
  - `qrcode.js` por CDN.  
  - Overlay \= misma página con `?overlay=1` (fondo transparente o chroma, 2 líneas, fuente grande).  
  - Vista de escenario \= captura \+ subtítulos \+ QR en el mismo browser, igual que operan hoy.  
- **Backend:** Python 3.12, FastAPI \+ uvicorn, asyncio, `google-genai` (última versión: los campos interim / `custom_vocabulary` / `translation_config` son nuevos), ffmpeg, pydantic-settings. Camino 2: `argostranslate`.  
- **Almacenamiento:** sin base de datos. `data/sessions/<id>/{meta.json, glossary.json, captions.jsonl}`. Estado vivo en memoria del SessionManager.  
- **IA (todo free tier):**  
  - `gemini-3.5-live-translate-preview` (Camino 1\) o `gemini-3.5-transcribe-live` (Camino 2).  
  - `gemini-3.1-flash-lite` para la pasada final y el Knowledge Pack (1–2 llamadas por charla).

### 2.8 Hosting

| Opción | Costo | A favor | En contra | Veredicto |
| :---- | :---- | :---- | :---- | :---- |
| **Hugging Face Spaces** (Docker, CPU basic) | Gratis, sin tarjeta | 2 vCPU / 16 GB, HTTPS (el mic funciona), WebSockets, secrets, "Duplicate this Space" \= deploy en 2 clics | Disco efímero, se duerme sin tráfico, sin autoscaling | **Elegida** |
| Oracle Cloud Always Free | Gratis (pide tarjeta para verificar) | VM ARM generosa, regiones en Sudamérica | TLS, firewall y servicio a mano | Alternativa "producción" en el README |
| Cloud Run | Free tier, pero exige billing | Autoscaling | Riesgo de cobro; si comparte proyecto con la key, Gemini pasa a pago | Descartada |
| Render free | Gratis | Simple | Se duerme rápido, CPU mínima (no alcanza para traducción local) | Descartada |

- **Latencia:** el salto al servidor suma décimas de segundo; domina el modelo.  
- **Requisitos de HF Spaces:** Dockerfile en la raíz, usuario no-root UID 1000, puerto 7860, frontmatter YAML en el README (`sdk: docker`, `app_port: 7860`).  
- **Deploy para cualquier conferencia:** "Duplicate this Space" → pegar `GEMINI_API_KEY` como secret → listo.  
- **Sin nube:** `docker compose up` en la mini PC \+ Cloudflare Tunnel gratis.

### 2.9 Escalabilidad (honesta)

- **Un Space aguanta varias salas:** el trabajo pesado lo hace Gemini; el container solo mueve audio y texto (más la traducción local liviana del Camino 2).  
- **Más salas \= más Spaces:** un Space por grupo de salas \+ una página de agenda estática que apunta a cada uno. Sin estado compartido.  
- **El techo real es el cupo de sesiones Live del proyecto.** Google no lo publica: el valor efectivo se mira en AI Studio → Rate limits y se mide (T2.10a). En T2.10a, 2 sesiones simultáneas anduvieron bien desde frío, pero abrir sesiones nuevas enseguida de otras degrada a una: hay que evitar crear sesiones de más (rotar reanudando). El `SessionManager` aplica ese techo: una sala más allá de `MAX_CONCURRENT_LIVE` no arranca (error claro, nunca encola). Costo cero con varias salas en paralelo **no está garantizado** por el free tier.  
- **Cómo se documenta:**  
  - Key configurable por sala: solo suma cupo si cada key es de **otro proyecto** (los límites son por proyecto, no por key). Revisar los términos de Google antes de usar varias cuentas propias.  
  - Modo 100% local como roadmap: Whisper \+ Gemma/Argos en hardware propio (la consigna lo sugiere).

---

## 3\. NotebookLM: sencillo y automatizado, en 3 capas

| Capa | Qué hace | Tipo | Esfuerzo |
| :---- | :---- | :---- | :---- |
| **1\. Knowledge Pack en la app** | Al hacer stop, 1–2 llamadas a Flash-Lite generan resumen, puntos clave y quiz. Se ven en la página de la charla (mismo QR) junto con "Preguntale a la charla" (transcripción entera en contexto; límite de preguntas por persona para cuidar la cuota) | Default, automático, oficial | \~2 h |
| **2\. Exporter a NotebookLM** | Con `notebooklm-py` (librería no oficial): notebook por charla, transcripción como fuente, podcast (Audio Overview) generado, link en la página de la charla | Opcional, automático, **no oficial** | \~1–1,5 h (stretch) |
| **3\. Botón "Copiar para NotebookLM"** | Descarga un `.md` con transcripción \+ resumen y abre notebooklm.google.com | Siempre disponible | \~15 min |

**Advertencias de la capa 2:** no es oficial, depende de la sesión de navegador de una cuenta Google (guardada como secret) y puede romperse. Va **apagada por defecto** y nunca en el camino crítico. Si falla, las capas 1 y 3 siguen funcionando.

**Por qué no la API oficial:** NotebookLM (renombrado Gemini Notebook en julio 2026\) no tiene API pública para cuentas personales; la API oficial es de NotebookLM Enterprise y requiere Google Cloud con licencia paga.

---

## 4\. Roadmap por fases

### Fase 1 — Base y mínimo viable (H0–H3.5)

- [x] (ambos) Key en proyecto sin billing \+ chequeo de cuotas en AI Studio \+ decisión del camino. *(Fase 0 ✅)*  
- [x] (ambos) Congelar interfaz `Engine`, contrato JSON y endpoints. *(Fase 0 ✅)*  
- [x] (A) Fix productor/consumidor en `FileSource` \+ bump de `google-genai`.  
- [x] (A) `LiveSessionRunner` genérico probado por CLI con los mp3. Medir latencia de interim y final. *(mediciones en el README)*  
- [x] (A) Config del camino elegido. Si es Camino 2: Argos EN↔ES con placeholders para el glosario. *(Camino 1; Argos N/A)*  
- [x] (B) FastAPI \+ SessionManager \+ WS de captions \+ `FakeEngine` que reproduce un `captions.jsonl` (B no se bloquea esperando al motor; de paso nace el modo replay).  
- [x] (B) Página de audiencia mínima: selector de sala \+ idioma, interim en gris reemplazado por el final.  
- [ ] (B) Dockerfile compatible con HF \+ Space creado \+ secret \+ primer deploy. **Deployar en H3, no en H13.** *(Dockerfile listo; falta Space + deploy)*  
- [ ] ✅ **Checkpoint H3.5:** mp3 → Space → subtítulos en el celular.

### Fase 2 — Core (H3.5–H8)

- [ ] (A) Rotación antes de los 10 min \+ backoff (ver 2.6).  
- [ ] (A) 2 salas en paralelo, excepciones aisladas por task.  
- [ ] (A) `captions.jsonl` append-only \+ glosario.  
- [ ] (A) Si los mp3 duran menos de 10 min: `FileSource` en loop para poder probar la rotación.  
- [ ] (B) MicSource con AudioWorklet \+ selector de dispositivo de entrada (la placa de audio).  
- [ ] (B) Vista de escenario: captura \+ subtítulos \+ QR.  
- [ ] (B) Consola de operador: crear sala, fuente (mic / mp3), idioma, glosario, start/stop.  
- [ ] (ambos) 2 salas: sesiones Live aisladas (T2.10a) → backend completo 2–3 min (T2.10b) → Space 20+ min, mic en ES \+ mp3 en EN (T2.10c) → rotación con 2 salas (T2.10d).  
- [ ] 🎥 **H8: video de emergencia** aunque sea feo.

### Fase 3 — Integración, UX y datos de prueba (H8–H12.5)

- [ ] (B) Overlay `?overlay=1` probado como Browser Source en OBS.  
- [ ] (B) Panel de monitoreo por sala: estado, sesiones Live abiertas vs. límite, rotaciones, errores, latencia p50/p95, oyentes por idioma, alerta de silencio.  
- [ ] (A) Export SRT / VTT / TXT desde `captions.jsonl`.  
- [ ] (A) Pasada final con glosario \+ Knowledge Pack (capa 1\) \+ botón NotebookLM (capa 3).  
- [ ] Datos de prueba en `samples/`: los 2 mp3 (recortes de 2–3 min para el repo), glosario de ejemplo, un `captions.jsonl` para replay.  
- [ ] Stretch, en este orden:  
      1. Audio traducido para auriculares (solo Camino 1).  
      2. Exporter automático a NotebookLM (capa 2).  
- [ ] README (ver sección 6).

### Fase 4 — Testing, freeze y pitch (H12.5–H15)

- [ ] E2E simulando otra conferencia: duplicar el Space desde cero siguiendo solo el README.  
- [ ] **H13.5: code freeze.** Solo bugfixes.  
- [ ] Video final (guion en sección 5).  
- [ ] Subtítulos en inglés del video generados por el propio sistema: audio del video → `FileSource` → export VTT → subir a YouTube.  
- [ ] Envío a Devpost con al menos 1 h de margen antes de las 15:00 UTC.

---

## 5\. Video demo (1–2 min)

No hay presentación en vivo: el video \+ el Devpost son el pitch.

| Tiempo | Contenido |
| :---- | :---- |
| 0:00 | El problema: 30+ charlas en inglés, herramientas caras y manuales |
| 0:15 | Consola con 2 salas → celular vía QR → subtítulos con badge de latencia |
| 0:45 | Overlay en OBS sobre el stream |
| 1:05 | Panel de monitoreo: 2 salas, latencia, costo USD 0 |
| 1:20 | Stop → Knowledge Pack \+ una pregunta respondida con minuto citado |
| 1:45 | "Duplicate this Space" \+ licencia MIT |

---

## 6\. Checklist del README final

- [ ] Deploy en 2 clics (Duplicate Space) y alternativa `docker compose up`.  
- [ ] Cómo crear la API key en un proyecto **sin billing** y cómo chequear cuotas en AI Studio.  
- [ ] Aviso de uso de datos en free tier.  
- [ ] Cómo usar MicSource (placa de audio → browser) y cómo probar con los mp3.  
- [ ] Cómo usar el QR y el overlay en OBS/vMix.  
- [ ] Cómo escalar: sharding de Spaces, key por sala, modo local (roadmap).  
- [ ] Licencia MIT.

---

## 7\. Riesgos y plan B

### Si falta tiempo, se recorta en este orden

1. Audio traducido y exporter automático a NotebookLM.  
2. Quiz (quedan resumen \+ "Preguntale a la charla").  
3. Panel → tabla simple sobre `GET /api/sessions`.

**Intocable:** mic, 2 salas, EN→ES, selector de audiencia, README y deploy.

### Fallas

| Riesgo | Plan B |
| :---- | :---- |
| El cupo de sesiones Live no alcanza para 2 salas | Key por sala de **otro proyecto** (la de cada integrante), Camino 2 si transcribe-live tiene otro cupo, o 1 sala por Space |
| Se agota la cuota diaria en plena demo | La traducción local sigue funcionando; modo replay para grabar el video sin API |
| El modelo preview cambia o falla | Cambiar de camino con el flag `ENGINE=` (misma interfaz) |
| La rotación de 10 min se rompe | Prueba obligatoria de 20+ min antes del freeze |
| El Space está dormido o se reinicia (disco efímero) | Despertarlo antes de la charla; descargar exports al hacer stop |
| El mic no captura | Requiere HTTPS (HF lo da) o localhost |
| Mic desenchufado en pleno evento | Alerta de silencio en el panel |
| NotebookLM no oficial se rompe | Las capas 1 y 3 no dependen de eso |

---

## 8\. Pendiente

- [x] Decisión de camino (T0.3): **Camino 1 — `live-translate`** (`ENGINE=live_translate`, modelo `gemini-3.5-live-translate-preview`). Implementado y probado en `backend/engine/live_translate.py`.
- [ ] Confirmar el cupo de sesiones Live concurrentes del proyecto nuevo (AI Studio → Rate limits). En T1.4, con 2 sesiones a la vez la segunda no recibió respuesta. Define si alcanza para 2 salas (T2.10) o si hace falta key por sala / Camino 2.
- [x] Probe T2.10a (`scripts/live_probe.py`, tabla en el README): 2 sesiones simultáneas andan bien desde frío; abrir sesiones nuevas enseguida de otras degrada a una (3–7× más lenta, se va en < 5 min); la reanudación con handle funciona (1,3 s de hueco, sin repetir texto).

---

## Referencias

- Live transcription: [https://ai.google.dev/gemini-api/docs/live-api/live-transcribe](https://ai.google.dev/gemini-api/docs/live-api/live-transcribe)  
- Live translation: [https://ai.google.dev/gemini-api/docs/live-api/live-translate](https://ai.google.dev/gemini-api/docs/live-api/live-translate)  
- Session management (límites de sesión): [https://ai.google.dev/gemini-api/docs/live-api/session-management](https://ai.google.dev/gemini-api/docs/live-api/session-management)  
- Rate limits y tiers: [https://ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)  
- Pricing (free tier y uso de datos): [https://ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing)  
- Ejemplos oficiales de Live API: [https://github.com/google-gemini/gemini-live-api-examples](https://github.com/google-gemini/gemini-live-api-examples)  
- Hugging Face Spaces: [https://huggingface.co/docs/hub/spaces-overview](https://huggingface.co/docs/hub/spaces-overview)  
- notebooklm-py (no oficial): [https://github.com/teng-lin/notebooklm-py](https://github.com/teng-lin/notebooklm-py)  
- Repo del equipo: [https://github.com/valentinnavalos/nerdearla-hackathon-2026](https://github.com/valentinnavalos/nerdearla-hackathon-2026)