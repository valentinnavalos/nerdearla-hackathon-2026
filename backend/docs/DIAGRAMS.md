# Diagramas — Nerdearla Live Captions

> Diagramas en Mermaid: GitHub los renderiza directo en este archivo.
> Las versiones PNG están en `docs/diagrams/` (para Devpost, el video o slides).

## Índice

- [1. Contexto del sistema](#1-contexto-del-sistema)
- [2. Componentes del backend](#2-componentes-del-backend)
- [3. Pipeline de datos de una sala](#3-pipeline-de-datos-de-una-sala)
- [4. Secuencia: ciclo de vida de una charla](#4-secuencia-ciclo-de-vida-de-una-charla)
- [5. Secuencia: rotación de la sesión Live](#5-secuencia-rotación-de-la-sesión-live)
- [6. Estados de una sala](#6-estados-de-una-sala)
- [7. Flujo del público](#7-flujo-del-público)
- [8. Flujo del operador](#8-flujo-del-operador)
- [9. Despliegue](#9-despliegue)
- [10. Escalado a muchas salas](#10-escalado-a-muchas-salas)
- [11. Decisión de camino en H0](#11-decisión-de-camino-en-h0)

---

## 1. Contexto del sistema

Quién usa el sistema y con qué servicios externos habla. Muestra las tres conexiones WebSocket: **#1** audio del escenario al servidor, **#2** servidor ↔ Gemini Live (la maneja el SDK) y **#3** subtítulos hacia el público.

```mermaid
flowchart LR
  OP["👩‍💻 Operador del evento<br/>consola + panel"]
  ESC["🎤 Mini PC del escenario<br/>placa de audio → browser"]
  PUB["📱 Público<br/>celular vía QR"]
  STR["📺 Streaming<br/>OBS / vMix"]

  subgraph HF["☁️ Hugging Face Space (gratis)"]
    APP["Nerdearla Live Captions<br/>FastAPI + frontend estático"]
  end

  GL["Gemini Live API<br/>live-translate o<br/>transcribe-live"]
  GF["Gemini Flash-Lite<br/>Knowledge Pack y preguntas"]
  NB["NotebookLM<br/>opcional, no oficial"]

  ESC -->|"WS #1: audio PCM 16 kHz"| APP
  APP -->|"subtítulos"| ESC
  OP -->|"HTTPS: crear / start / stop"| APP
  APP -->|"WS: estado y métricas"| OP
  APP -->|"WS #3: subtítulos ES / EN"| PUB
  APP -->|"overlay como Browser Source"| STR
  APP <-->|"WS #2: sesión persistente WSS"| GL
  APP -->|"1-2 requests por charla"| GF
  APP -.->|"al terminar la charla"| NB
```

PNG: `docs/diagrams/01-contexto.png`

---

## 2. Componentes del backend

Módulos del repo y cómo se relacionan. El frontend es estático y lo sirve el mismo FastAPI; cada sala corre su propio pipeline dentro de una `asyncio.Task`.

```mermaid
flowchart TB
  subgraph FE["Frontend estático · HTML + JS vanilla"]
    direction LR
    IDX["index.html<br/>audiencia + overlay"]
    STG["stage.html<br/>escenario: captura + QR"]
    ADM["admin.html<br/>consola + panel"]
    TLK["talk.html<br/>post-charla"]
  end

  subgraph API["api/ · FastAPI · admin protegido con ADMIN_TOKEN"]
    direction LR
    WSC["WS /ws/captions"]
    WSI["WS /ws/ingest"]
    WSA["WS /ws/admin"]
    REST["REST /api/..."]
  end

  subgraph CORE["core/"]
    direction LR
    MGR["SessionManager<br/>pub/sub por sala + idioma"]
    SES["Session<br/>1 asyncio.Task por sala"]
    UTIL["glossary · segmenter<br/>dedupe · metrics"]
  end

  subgraph SALA["Pipeline de cada sala"]
    direction LR
    SRC["sources/<br/>MicSource · FileSource"]
    ENG["engine/<br/>LiveTranslate · Camino 1<br/>TranscribeMT · Camino 2<br/>Chunked · fallback A<br/>Replay · demo sin API"]
    RUN["LiveSessionRunner<br/>conexión + rotación"]
    ARG["translate/argos_mt<br/>solo Camino 2"]
  end

  subgraph POST["post/ · al hacer stop"]
    direction LR
    EXP["exports<br/>SRT · VTT · TXT · MD"]
    KP["knowledge<br/>resumen · quiz · ask"]
    NBL["notebooklm<br/>opcional"]
  end

  DATA[("DATA_DIR<br/>captions.jsonl · meta.json<br/>knowledge.json · quota.json")]
  GEM(["Gemini Live API"])
  FLASH(["Gemini Flash-Lite"])

  IDX --> WSC
  STG --> WSC
  STG --> WSI
  ADM --> WSA
  ADM --> REST
  TLK --> REST

  WSC --> MGR
  WSA --> MGR
  REST --> MGR
  WSI --> SRC

  MGR --> SES
  SES --> UTIL
  SES --> SRC
  SRC --> ENG
  ENG --> RUN
  ENG -.-> ARG
  RUN <-->|WSS| GEM

  SES --> DATA
  SES --> POST
  POST --> DATA
  KP --> FLASH
```

PNG: `docs/diagrams/02-componentes.png`

---

## 3. Pipeline de datos de una sala

Camino que recorre el audio hasta convertirse en subtítulos, con las dos variantes del motor. Solo uno de los dos caminos está activo según `ENGINE`.

```mermaid
flowchart LR
  subgraph IN["Fuente de audio"]
    M["MicSource<br/>WS desde el browser"]
    F["FileSource<br/>mp3 → ffmpeg → PCM"]
  end

  Q["asyncio.Queue<br/>frames de 100 ms<br/>máx 5 s, descarta viejos"]
  MET["Métricas<br/>nivel · VAD · silencio"]
  RB["Ring buffer 2,5 s<br/>para la rotación"]
  RUN["LiveSessionRunner<br/>tarea emisora + receptora"]

  M --> Q
  F --> Q
  Q --> RUN
  RUN --> RB
  Q -.-> MET

  subgraph C1["Camino 1 · live-translate"]
    G1["Gemini Live Translate<br/>original + traducción"]
    S1["Segmenter<br/>fragmentos → interim / final"]
  end

  subgraph C2["Camino 2 · transcribe-live"]
    G2["Gemini Transcribe Live<br/>custom_vocabulary"]
    AR["Argos en CPU<br/>traducción local"]
  end

  RUN <-->|WSS| G1
  G1 --> S1
  RUN <-->|WSS| G2

  GL["Glosario<br/>reemplazos + mayúsculas"]
  S1 --> GL
  G2 -->|"interim / final"| GL
  GL -->|"finales originales"| AR

  EM["emit CaptionEvent"]
  GL --> EM
  AR -->|"finales traducidos"| EM

  EM --> H["Historial en memoria<br/>últimos 50 finales"]
  EM --> J[("captions.jsonl")]
  EM --> SUB["Suscriptores por idioma<br/>celulares · escenario · overlay"]
```

PNG: `docs/diagrams/03-pipeline.png`

---

## 4. Secuencia: ciclo de vida de una charla

Desde que el operador crea la sala hasta que el público ve el resumen al terminar.

```mermaid
sequenceDiagram
  autonumber
  actor OP as Operador
  participant ST as Vista escenario (mini PC)
  participant SV as Servidor (HF Space)
  participant GL as Gemini Live
  participant AU as Público (celular / OBS)
  participant FL as Gemini Flash-Lite

  OP->>SV: POST /api/sessions (título, idioma, fuente mic, glosario)
  SV-->>OP: 201 sala-1
  OP->>SV: POST /api/sessions/sala-1/start
  SV->>GL: connect(modelo, config) vía SDK
  GL-->>SV: sesión abierta
  OP->>ST: abre stage.html?s=sala-1
  ST->>ST: getUserMedia + AudioWorklet a 16 kHz
  ST->>SV: WS /ws/ingest con token
  AU->>SV: WS /ws/captions?lang=es (escaneó el QR)
  SV-->>AU: historial de finales
  loop cada 100 ms mientras dura la charla
    ST->>SV: frame PCM de 3200 bytes
    SV->>GL: send_realtime_input(audio)
  end
  loop a medida que Gemini transcribe
    GL-->>SV: transcripción parcial o final
    SV->>SV: segmentar + glosario (+ Argos en Camino 2)
    SV-->>AU: CaptionEvent interim / final
    SV-->>ST: CaptionEvent para la pantalla
  end
  Note over SV,GL: Cada ~9 min, rotación de sesión (diagrama 5)
  OP->>SV: POST /api/sessions/sala-1/stop
  SV->>GL: cerrar sesión
  SV-->>AU: session_status STOPPED + link a talk.html
  SV->>FL: 1 request con la transcripción completa
  FL-->>SV: resumen + puntos clave + quiz en JSON
  AU->>SV: GET /api/sessions/sala-1/knowledge
  SV-->>AU: resumen, quiz, descargas
```

PNG: `docs/diagrams/04-secuencia-charla.png`

---

## 5. Secuencia: rotación de la sesión Live

Cómo se evita el corte de ~10 minutos de la Live API sin perder audio ni duplicar frases. Es la pieza más riesgosa (T2.1).

```mermaid
sequenceDiagram
  autonumber
  participant SRC as Cola de frames
  participant RUN as LiveSessionRunner
  participant SEM as Semáforo MAX_CONCURRENT_LIVE
  participant GA as Gemini sesión N
  participant GB as Gemini sesión N+1

  loop audio en vivo
    SRC->>RUN: frame de 100 ms
    RUN->>RUN: guardar en ring buffer (2,5 s)
    RUN->>GA: send_realtime_input
    GA-->>RUN: transcripciones
  end
  alt timer de 540 s
    RUN->>RUN: estado ROTATING
  else GoAway recibido
    GA-->>RUN: GoAway con time_left
    RUN->>RUN: estado ROTATING
  end
  RUN->>GA: close()
  RUN->>SEM: release()
  Note over RUN: los frames nuevos se siguen guardando en el ring buffer
  RUN->>SEM: acquire()
  RUN->>GB: connect(modelo, config)
  GB-->>RUN: sesión abierta
  RUN->>GB: reenviar ring buffer (últimos 2,5 s)
  RUN->>RUN: estado RUNNING
  GB-->>RUN: primer final de la sesión nueva
  RUN->>RUN: dedupe_overlap(cola previa, texto nuevo)
  opt error de red o 429 en cualquier paso
    RUN->>RUN: RECONNECTING + backoff 1, 2, 4, 8, 16, 30 s
  end
```

PNG: `docs/diagrams/05-rotacion.png`

---

## 6. Estados de una sala

Estados que muestra el panel de monitoreo y qué los provoca.

```mermaid
stateDiagram-v2
  [*] --> CREATED: crear sala
  CREATED --> RUNNING: start
  RUNNING --> ROTATING: 540 s o GoAway
  ROTATING --> RUNNING: sesión nueva abierta
  RUNNING --> RECONNECTING: error de red o 429
  ROTATING --> RECONNECTING: falla al reconectar
  RECONNECTING --> RUNNING: reconexión OK
  RECONNECTING --> ERROR: 10 fallos seguidos
  ERROR --> RUNNING: reintento desde la consola
  RUNNING --> STOPPED: stop
  RECONNECTING --> STOPPED: stop
  ERROR --> STOPPED: stop
  STOPPED --> [*]
  note right of STOPPED
    Dispara exports,
    Knowledge Pack y
    NotebookLM opcional
  end note
```

PNG: `docs/diagrams/06-estados.png`

---

## 7. Flujo del público

Qué ve una persona desde que escanea el QR hasta después de la charla. El mismo QR sirve antes, durante y después.

```mermaid
flowchart TD
  A["📱 Escanea el QR<br/>junto a la pantalla"] --> B{"Estado de la sala"}
  B -->|"Todavía no empezó"| W["Pantalla de espera<br/>se conecta sola al arrancar"]
  W --> C
  B -->|"En curso"| C["Elige idioma<br/>ES / EN"]
  C --> D["Subtítulos en vivo<br/>parcial en gris → final"]
  D --> E["Ajusta tamaño<br/>y contraste"]
  D --> F["🎧 Escuchar traducción<br/>opcional, Camino 1"]
  D --> G{"¿Terminó la charla?"}
  G -->|No| D
  G -->|Sí| H["Aviso: la charla terminó,<br/>ver resumen"]
  B -->|"Terminada"| H
  H --> I["Página de la charla"]
  I --> J["Resumen y puntos clave<br/>con minuto"]
  I --> K["Quiz"]
  I --> L["Preguntale a la charla"]
  I --> M["Descargas<br/>SRT · VTT · TXT · MD"]
  I --> N["NotebookLM<br/>copiar o abrir notebook"]
```

PNG: `docs/diagrams/07-audiencia.png`

---

## 8. Flujo del operador

Preparación única antes del evento y rutina por sala el día del evento.

```mermaid
flowchart TD
  subgraph PRE["Antes del evento · una vez"]
    P1["Crear proyecto en AI Studio<br/>SIN billing + API key"] --> P2["Duplicate this Space"]
    P2 --> P3["Cargar secrets<br/>GEMINI_API_KEY · ADMIN_TOKEN"]
    P3 --> P4["Glosario del evento<br/>Nerdearla, oradores, tecnologías"]
  end

  subgraph DIA["El día del evento · por sala"]
    D1["Despertar el Space<br/>abrir /healthz"] --> D2["admin.html: crear sala<br/>título, orador, idioma, fuente"]
    D2 --> D3["Mini PC: abrir stage.html<br/>pantalla completa"]
    D3 --> D4["Elegir entrada de la placa<br/>Iniciar captura"]
    D4 --> D5["Start"]
    D5 --> D6{"Panel: ¿todo verde?"}
    D6 -->|Sí| D7["Charla en curso"]
    D6 -->|"No: silencio, error,<br/>mic desconectado"| D8["Revisar cable / entrada<br/>o reintentar la sala"]
    D8 --> D6
    D7 --> D9["Stop al terminar"]
    D9 --> D10["Verificar resumen<br/>y descargas en talk.html"]
  end

  PRE --> DIA
```

PNG: `docs/diagrams/08-operador.png`

---

## 9. Despliegue

Cómo llega el código al Space y cómo lo replica otra conferencia. Incluye la alternativa sin nube en la mini PC.

```mermaid
flowchart LR
  G["Google AI Studio<br/>proyecto SIN billing"]

  subgraph DEV["Código"]
    GH["GitHub<br/>repo público MIT"]
  end

  subgraph HFP["Hugging Face · gratis"]
    SEC["Secrets<br/>GEMINI_API_KEY · ADMIN_TOKEN"]
    SP["Space Docker<br/>CPU basic 2 vCPU / 16 GB<br/>HTTPS + WebSockets"]
    SP2["Space de otra conferencia"]
  end

  subgraph ALT["Alternativa sin nube"]
    DC["docker compose up<br/>en la mini PC"]
    CF["cloudflared<br/>túnel HTTPS gratis"]
  end

  G -->|"API key free tier"| SEC
  SEC --> SP
  GH -->|"git push hf main"| SP
  SP -->|"Duplicate this Space<br/>2 clics"| SP2
  GH -->|"git clone"| DC
  DC --> CF
```

PNG: `docs/diagrams/09-despliegue.png`

---

## 10. Escalado a muchas salas

Se escala duplicando Spaces por grupo de salas, sin estado compartido. El techo real es el cupo de sesiones Live por proyecto de Gemini. Si se usan keys de distintos proyectos, que sean de personas u organizaciones distintas y revisar antes los términos de uso de Google.

```mermaid
flowchart TB
  AG["Página de agenda estática<br/>links a cada sala"]

  subgraph SA["Space A · salas 1 a 3"]
    A1["Sala 1"]
    A2["Sala 2"]
    A3["Sala 3"]
  end

  subgraph SB["Space B · salas 4 a 6"]
    B1["Sala 4"]
    B2["Sala 5"]
    B3["Sala 6"]
  end

  subgraph SC["Space N · ..."]
    C1["Sala ..."]
  end

  KA["API key A"] --> SA
  KB["API key B"] --> SB
  KC["API key N"] --> SC

  AG --> SA
  AG --> SB
  AG --> SC

  GEM(["Gemini Live API<br/>cupo por proyecto"])
  SA <--> GEM
  SB <--> GEM
  SC <--> GEM
```

PNG: `docs/diagrams/10-escalado.png`

---

## 11. Decisión de camino en H0

Árbol de decisión a partir de las cuotas que muestre AI Studio (T0.2 y T0.3).

```mermaid
flowchart TD
  A["H0: revisar Rate limits<br/>en AI Studio"] --> B{"live-translate:<br/>2+ sesiones concurrentes<br/>y cupo diario suficiente?"}
  B -->|Sí| C1["Camino 1<br/>ENGINE=live_translate"]
  B -->|No| D{"transcribe-live<br/>disponible en free tier?"}
  D -->|Sí| C2["Camino 2<br/>ENGINE=transcribe_mt + Argos"]
  D -->|No| C3["Replantear<br/>fallback A solo para demos cortas<br/>o modo local"]
```

PNG: `docs/diagrams/11-decision-h0.png`

---
