# Reporte de concurrencia y capacidad

> **Fuente de verdad sobre capacidad.** Cualquier otro documento que hable de cuántas salas o sesiones soportamos remite acá. Cada afirmación lleva su estado, y cada resultado lleva branch + commit + fecha.
>
> Última revisión: 2026-09-25.

## Convención de estados

| Estado | Significa | Requisito |
|---|---|---|
| `DOCUMENTED` | Lo publica el proveedor | Fuente + fecha de consulta |
| `OBSERVED` | Lo vimos, pero en una corrida única o informal | Fecha y condiciones; no alcanza para decidir |
| `HYPOTHESIS` | Lo creemos, sin evidencia suficiente | Qué experimento lo confirmaría |
| `EXPERIMENT` | Experimento diseñado, pendiente de correr | Protocolo |
| `RESULT` | Resultado de un experimento **repetido** | Branch + commit + fecha + condiciones + n |
| `DECISION` | Lo decidimos (puede ser `PROVISIONAL`) | Motivo y evidencia ([`ARCHITECTURE.md` §7](ARCHITECTURE.md#7-decisiones)) |

## 1. Resumen

Estado al 2026-09-25, con el barrido **parcial** (A1, A2, A3 y A4-s5; §6):

- **Google no publica** un límite de sesiones Live concurrentes para este modelo (`DOCUMENTED`, §2).
- **N=2 simultáneas, en frío:** 6 de 6 sesiones `ACCEPTED` en 3 trials (`RESULT`, n=3). Sostiene H1.
- **N=3 simultáneas:** en 2 de 3 trials **ninguna** de las 3 sesiones conectó (fallo a los ~10 s). En el tercero conectaron las 3 (`RESULT`, n=3). No sabemos todavía si es un rechazo explícito o un timeout: el probe perdió el mensaje de error (§6, validez).
- **Degradación silenciosa real** (≥ 10 s sin texto a mitad de la sesión) en 2 de 10 trials con Gemini conectado, **incluso con N=1** (A1 t3: 11 s) y con N=2 escalonadas (A4-s5 t1: 15–16 s en las dos). Otras 5 sesiones que el clasificador marca como degradadas son **artefactos de medición** (§6).
- **Escalonar 5 s** (A4-s5) no mostró ventaja sobre arrancar juntas (A2). H3 sin evidencia a favor.
- **Veredicto del gate (§8): pendiente** hasta corregir la medición (T2.12) y completar el barrido (T2.13). `MAX_CONCURRENT_LIVE=2` se mantiene como decisión provisional (D2).

## 2. Cuatro capacidades distintas

"Soportamos N salas" no significa nada si no se dice **cuál** de estas capacidades es:

| Capacidad | Pregunta | Estado actual |
|---|---|---|
| **Documentada** | ¿Qué publica Google? | `DOCUMENTED` (consultado el 2026-09-25): la página de [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) define **RPM, TPM y RPD**, "aplicados por proyecto, no por API key", y remite a AI Studio para ver los límites activos. **No publica una cifra de sesiones Live concurrentes** para ningún modelo. La página de [session management](https://ai.google.dev/gemini-api/docs/live-api/session-management) documenta la conexión (~10 min), la sesión de solo audio (15 min), el `GoAway` y los handles de reanudación (válidos 2 h), y **nada sobre concurrencia**. El "recomendado en AI Studio: 2" del mensaje del commit `9b02636` no tiene fuente registrada y no se toma como dato |
| **Observada** | ¿Qué reproducimos, y bajo qué condiciones? | Ver §5 (historial `OBSERVED`), §6 (barrido `RESULT`) y §7 (audiencia) |
| **Operativa** | ¿Qué permite el backend? | `MAX_CONCURRENT_LIVE` (`CapacityGuard`): límite de seguridad **propio**, no de Gemini. Valor: ver §8 |
| **Económica** | ¿Qué es viable para el producto (costo, billing)? | Sin modelar. `HYPOTHESIS`: con billing el cupo sube, a un costo por sala-hora a verificar |

## 3. Capas de prueba

"Dos sesiones conectadas" no es lo mismo que "dos salas funcionando 20 minutos". Cada capa agrega código nuestro, así que si algo se degrada se puede ubicar dónde:

| # | Capa | Herramienta | Qué agrega | Estado |
|---|---|---|---|---|
| L1 | SDK / Live puro | `scripts/live_probe.py` | Nada nuestro | Historial `OBSERVED` (§5) |
| L2 | `LiveTranslateEngine` | `runner_probe --layer engine` | Runner, segmentadores, glosario, `FrameQueue` | Barrido (§6: A1–A4, D) |
| L3 | Runner completo | `runner_probe --layer session` | `SessionManager`, `Session`, `CaptionWriter`, fan-out a subscribers | Barrido (§6: B) |
| L4 | Backend completo | T2.10b: API + WS reales | HTTP, WebSockets, clientes reales | `EXPERIMENT`, depende de T2.5 |
| L5 | Sostenida 20+ min, 2 salas, rotación + reanudación | T2.10c / T2.10d | Ciclo de vida de la conexión | `EXPERIMENT`, **bloqueada por T2.1** |
| — | Fan-out sin Gemini | `scripts/audience_load.py` | Clientes WS contra salas replay | §7 |

## 4. Clasificación objetiva de cada sesión

Definida en `scripts/probe_metrics.py` **antes** de correr el barrido. `msgs/s` por sí solo esconde la falla que ya vimos (una sesión que se congela decenas de segundos y después manda todo en ráfaga), por eso también cuentan los huecos entre mensajes con texto.

| Clase | Criterio |
|---|---|
| `ACCEPTED` | Conectó, dio texto y no cumple ningún criterio de abajo |
| `REJECTED_EXPLICITLY` | Error del servidor al conectar, o corte con 429 / `RESOURCE_EXHAUSTED` / 1008 / 1011 / `PERMISSION_DENIED` / `UNAVAILABLE` |
| `NO_RESPONSE` | Conectó y dio 0 mensajes con texto en la ventana |
| `TIMEOUT` | No llegó a conectar dentro de la ventana |
| `SILENT_DEGRADATION` | Después del primer texto, estuvo **≥ 10 s sin texto** (`stall_max_s`) mientras seguía recibiendo audio |
| `DEGRADED` | Contra la línea base A1 del mismo barrido (mediana): primer texto > 2× **y** > base + 3 s, o gap p95 > 2× **y** > base + 1 s, o textos/s < 0,5× base |

Métricas por sesión: `connect_ms`, `first_text_s`, textos/s, gaps p50/p95/p99 (después del primer texto), `time_without_messages_max_s` (incluye conexión → primer texto), `stall_max_s`, `first_error_s`, `last_success_s`, finales orig/trans, interims/s, frames enviados/perdidos, `dispatch_ms_max`, `callback_errors`, duración efectiva. Por trial: lag del event loop (p50/p99/máx; tick de 100 ms).

## 5. Historial `OBSERVED` (24/9, antes de esta revisión)

Condiciones: `scripts/live_probe.py` (SDK crudo, un proceso, 40 s por sesión, `human-centric-eng-by-ben-popplestone.mp3`), 17:48–18:11 (hora local, -03). Código: base `bfd5b61` más cambios sin commitear que después entraron en `9b02636` (el commit exacto no quedó registrado). **Corridas únicas por fila: no alcanzan para decidir.**

| Prueba | Observado |
|---|---|
| 1 sesión, justo después de otras corridas (17:48, 17:51) | degradada: primer texto a 7 s y 13,5 s; 10 y 3 fragmentos (normal: ~36) |
| 1 sesión, tras ~3 min sin uso | normal: 36 fragmentos, primer texto a 4,5 s |
| 2 simultáneas × 3, enseguida de la anterior | en las 3, una normal (36) y la otra degradada (5–13 fragmentos, primer texto a 6–12 s) |
| 2 escalonadas 10 s, enseguida | la primera degradada aun estando sola los primeros 10 s; la segunda normal |
| 2 simultáneas tras 5 min sin uso | las dos normales (36/36, primer texto a 4,1 y 5,1 s) |
| Reanudación (cerrar a mitad y reconectar con el handle) | reconexión en 1,3 s, el texto sigue sin repetir ni perder contexto |
| 1 sesión nueva enseguida de la reanudación | normal (36) |
| 2 salas con `runner_probe` (EN + ES, en frío, 45 s, **una corrida**) | las dos normales: primer texto a 4,1 y 3,3 s, ~8 msgs/s, 0 frames perdidos, callbacks ≤ 1,4 ms. **Smoke test**, no evidencia de estabilidad |

Hipótesis que salieron de acá y que el barrido pone a prueba: (H1) 2 sesiones simultáneas en frío andan; (H2) abrir sesiones nuevas enseguida de otras degrada alguna; (H3) escalonar los arranques ayuda.

## 6. Barrido 2026-09-25

Estado: `RESULT` **parcial** (n=3 trials por bloque; la medición tiene defectos conocidos, ver [validez](#validez-de-la-medición)). Faltan bloques (ver [pendientes](#bloques-pendientes)).

### Condiciones

| Campo | Valor |
|---|---|
| Código | branch `status` @ `fad0aee`, **dirty**. `diff_sha` `02887628c93079bd` (A1) y `2edd5d3f04111e7c` (A2–A4-s5); snapshot del árbol en `data/probe/sweep-20260924-2358/code.diff` + `untracked.tgz` |
| Entorno | Python 3.12.14, `google-genai` 2.25.0, un proceso (Docker local) |
| Modelo | `gemini-3.5-live-translate-preview` |
| Herramienta | `scripts/runner_probe.py --layer engine` (capa L2), `--seconds 60 --trials 3 --cooldown 300` |
| Muestras | A = `samples/en_talk_3min.mp3` (EN), B = `samples/es_talk_2min.mp3` (ES), C = `samples/mp3/interview-with-rob-pike.mp3` (EN) |
| Línea base | A1 (mediana de sus 3 trials): primer texto 4,2 s · gap p95 0,8 s · 1,60 textos/s |
| Reportes | `data/probe/sweep-20260924-2358/{A1,A2,A3,A4-s5}.json` (no se commitean) |

| Bloque | Sesiones | Stagger | Horario (UTC) | Horario (ART) |
|---|---|---|---|---|
| A1 | 1 (A) | — | 25/9 03:03–03:16 | 25/9 00:03–00:16 |
| A2 | 2 (A, B) | 0 s | 03:21–03:34 | 00:21–00:34 |
| A3 | 3 (A, B, C) | 0 s | 03:39–03:51 | 00:39–00:51 |
| A4-s5 | 2 (A, B) | B arranca 5 s después | 11:12–11:26 | 08:12–08:26 |

### Resultados por sesión

"Clase" es la salida de `probe_metrics` tal como está hoy. "Stall corregido" es el hueco máximo sin texto después del primero, **cortando la ventana a los 60 s** (sin la cola de cierre, ver defecto (c)). Reproducir con:

```bash
D=data/probe/sweep-20260924-2358
python -m scripts.probe_metrics $D/A1.json $D/A2.json $D/A3.json $D/A4-s5.json --baseline $D/A1.json
```

| Bloque | Trial | Sesión | Clase (`probe_metrics`) | connect ms | 1er texto s | textos/s | Stall crudo s | **Stall corregido s** | Duración s | Descartados | Lectura |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 | 1 | A en | ACCEPTED | 756 | 4,6 | 1,85 | 1,0 | 1,0 | 60,2 | 0 | OK |
| A1 | 2 | A en | ACCEPTED | 1304 | 4,2 | 1,60 | 2,0 | 2,0 | 60,2 | 0 | OK |
| A1 | 3 | A en | SILENT_DEGRADATION | 1189 | 4,2 | 1,53 | 11,0 | **11,0** | 60,2 | 0 | **Degradación real, con 1 sola sesión** |
| A2 | 1 | A en | ACCEPTED | 1346 | 3,9 | 1,77 | 1,8 | 1,8 | 60,2 | 0 | OK |
| A2 | 1 | B es | ACCEPTED | 1306 | 2,7 | 1,84 | 1,7 | 1,7 | 60,2 | 0 | OK |
| A2 | 2 | A en | ACCEPTED | 1356 | 3,9 | 1,85 | 1,7 | 1,7 | 60,2 | 0 | OK |
| A2 | 2 | B es | ACCEPTED | 1331 | 2,5 | 1,84 | 1,8 | 1,8 | 60,2 | 0 | OK |
| A2 | 3 | A en | ACCEPTED | 1269 | 4,0 | 1,80 | 1,7 | 1,7 | 60,2 | 0 | OK |
| A2 | 3 | B es | ACCEPTED | 1223 | 2,7 | 1,83 | 1,8 | 1,8 | 60,2 | 0 | OK |
| A3 | 1 | A, B, C | TIMEOUT (las 3) | — | — | 0 | — | — | 10,0–10,1 | 42–44 | **No conectó ninguna**; error perdido (defecto (a)) |
| A3 | 2 | A, B, C | TIMEOUT (las 3) | — | — | 0 | — | — | 10,0–10,1 | 42–44 | **No conectó ninguna**; error perdido (defecto (a)) |
| A3 | 3 | A en | SILENT_DEGRADATION | 2041 | 3,7 | 1,34 | 10,3 | 7,5 | 70,0 | 50 | Artefacto: < 10 s con la ventana corregida |
| A3 | 3 | B es | SILENT_DEGRADATION | 1447 | 2,6 | 1,31 | 17,9 | 7,9 | 70,0 | 51 | Artefacto: último texto a los ~50 s, 7,9 s hasta el corte |
| A3 | 3 | C en | SILENT_DEGRADATION | 2035 | 6,1 | 1,02 | 17,9 | 7,9 | 70,0 | 50 | Artefacto; primer texto lento (6,1 s vs base 4,2) |
| A4-s5 | 1 | A en | SILENT_DEGRADATION | 1426 | 4,3 | 1,40 | 16,2 | **16,2** | 70,0 | 50 | **Degradación real** (16 s sin texto a mitad de la sesión) |
| A4-s5 | 1 | B es | SILENT_DEGRADATION | 1337 | 3,3 | 1,14 | 15,0 | **15,0** | 70,0 | 50 | **Degradación real**, en el mismo tramo que A |
| A4-s5 | 2 | A en | ACCEPTED | 598 | 5,6 | 1,60 | 1,7 | 1,7 | 60,2 | 0 | OK |
| A4-s5 | 2 | B es | ACCEPTED | 1346 | 2,7 | 1,84 | 1,8 | 1,8 | 60,2 | 0 | OK |
| A4-s5 | 3 | A en | SILENT_DEGRADATION | 463 | 5,0 | 1,55 | 10,2 | 7,3 | 70,0 | 50 | Artefacto: < 10 s con la ventana corregida |
| A4-s5 | 3 | B es | SILENT_DEGRADATION | 1155 | 2,4 | 1,47 | 10,3 | 6,0 | 70,0 | 50 | Artefacto: < 10 s con la ventana corregida |

Lag del event loop (tick de 100 ms): p99 entre 5,9 y 10,5 ms en todos los trials con Gemini conectado, salvo un pico **máximo de 1.240 ms** en A4-s5 t1 (4 ticks > 100 ms), sin explicar. `dispatch_ms_max` ≤ 7,4 ms en todas las sesiones: el procesamiento nuestro no es el cuello de botella.

### Hallazgos

| # | Hallazgo | Estado |
|---|---|---|
| R1 | **2 sesiones simultáneas en frío andan** (A2: 6/6 `ACCEPTED`, primer texto 2,5–4,0 s, stall ≤ 1,8 s, 0 descartados). Sostiene H1 | `RESULT` (n=3) |
| R2 | **3 sesiones simultáneas fallan al conectar** en 2 de 3 trials: las 3 a la vez, a los ~10 s, sin enviar un frame. En el tercer trial conectaron las 3, con primer texto lento en C (6,1 s) | `RESULT` (n=3). **No** sabemos si es rechazo o timeout (defecto (a)) |
| R3 | La **degradación silenciosa ocurre también con 1 sesión** (A1 t3: 11 s sin texto). La variabilidad de Gemini es alta aun sin concurrencia, así que n=3 no alcanza para atribuir una degradación a la concurrencia | `RESULT` (n=3), baja potencia |
| R4 | **Escalonar 5 s no ayudó:** A4-s5 tuvo 1 trial de 3 con las 2 sesiones degradadas a la vez (15–16 s), frente a 0 de 3 en A2 sin escalonar. Contradice H3 débilmente (n=3, 7 h después de A2) | `RESULT` (n=3), baja potencia |
| R5 | Cuando las 2 sesiones se degradan, lo hacen **en el mismo tramo** (A4-s5 t1: de ~33 a ~49 s desde el inicio del trial, en A y en B), consistente con un problema del lado del servidor o de la red y no de una sesión | `OBSERVED` (1 caso) |
| R6 | Pico de lag del loop de 1,24 s en A4-s5 t1 | `OBSERVED`, sin explicar |

H2 (abrir sesiones enseguida de otras degrada alguna) no se probó en este barrido: todos los trials tuvieron 300 s de cooldown (queda para el bloque D).

### Validez de la medición

Tres defectos de `runner_probe` / `probe_metrics`, a corregir en T2.12 ([`ROADMAP.md`](ROADMAP.md#t212--corregir-la-medición-de-runner_probe--probe_metrics--a--40-min--p1)):

| # | Defecto | Efecto en este barrido | Estado |
|---|---|---|---|
| (a) | `except asyncio.TimeoutError` en `runner_probe.engine_layer` atrapa también un `TimeoutError` **interno** del engine (desde Python 3.11 son la misma clase). Un fallo de conexión a los ~10 s queda como `outcome="cut at 60s"` con `error=None` | A3 t1 y t2: `probe_metrics` los clasifica bien como `TIMEOUT` (no conectaron), pero se perdió el mensaje de error, así que no se puede distinguir un rechazo (`REJECTED_EXPLICITLY`) de un timeout. El corte por cuota (`QUOTA_MARKERS`) tampoco se pudo disparar | Confirmado leyendo el código. El origen del timeout de 10 s (¿`open_timeout` del websocket del SDK?) es `HYPOTHESIS` |
| (b) | Después del corte a los 60 s, la cancelación tarda **~10 s más** en cerrar la conexión (`elapsed_s` ≈ 70) | 7 de las 24 sesiones (A3 t3, A4-s5 t1 y t3). Mientras se cierra nadie consume la `FrameQueue(50)`, que se llena: los ~50 frames "descartados" de esas sesiones son del cierre, no de la sesión | Observado en los datos. El origen (¿`close_timeout` del websocket cuando el servidor no contesta el cierre?) es `HYPOTHESIS` |
| (c) | `probe_metrics.session_metrics` mide la ventana hasta `elapsed_s` (incluye el cierre), así que el tramo entre el último texto y el fin del cierre cuenta como stall | Infla `stall_max_s` en las sesiones de (b): 5 de ellas pasan el umbral de 10 s solo por eso (A3 t3 ×3, A4-s5 t3 ×2) y se clasifican `SILENT_DEGRADATION` por error | Confirmado recalculando con la ventana cortada a los 60 s (columna "Stall corregido") |

Las clases `ACCEPTED` y los `TIMEOUT` de A3 no dependen de estos defectos. Las degradaciones reales (A1 t3, A4-s5 t1) tampoco: su hueco está a mitad de la sesión.

### Bloques pendientes

Parte de T2.13:

- **A1** nueva línea base, con el probe corregido.
- **A3** repetido con el error capturado.
- **A4** con stagger 0, 20 y 30 s.
- **B:** `--layer session`, N=2 (capa L3).
- **D:** frío vs. caliente (sin cooldown), que prueba H2.

## 7. Prueba de audiencia (sin Gemini)

Estado: `EXPERIMENT`, **pendiente** (no se corrió). Parte de T2.13.

**Protocolo:** `ENGINE=replay` con `DEMO_ROOMS=2`, y `python -m scripts.audience_load --clients 10,50,100,200 --seconds 60 --server-pid <pid de uvicorn>` contra el servidor local. Por cada nivel: mensajes entregados/perdidos por cliente, latencia servidor → cliente (p50/p95), lag del event loop (`/healthz`) y CPU. Responde si `SessionManager` + colas por cliente alcanzan para la audiencia de una sala (D6) y si hacen falta las optimizaciones de D9.

## 8. Veredicto

**Gate de concurrencia: pendiente.**

- **Lectura provisoria:** N=2 en frío es viable (R1) y N=3 no lo es de forma confiable (R2). Coincide con `MAX_CONCURRENT_LIVE=2`.
- **Qué falta para cerrarlo:** corregir la medición (T2.12) y completar los bloques pendientes (T2.13): saber si el fallo de N=3 es un rechazo, y separar la degradación por concurrencia de la variabilidad normal de una sola sesión (R3).
- **Gate de ciclo de vida** (2 salas × 20+ min con rotación): **bloqueado por T2.1** (capa L5).
- **Frase canónica hasta entonces:** *"2 sesiones concurrentes: capacidad operativa observada, todavía no garantizada"*.

## 9. Pendientes y próximos experimentos

| Pendiente | Tarea | Revisa |
|---|---|---|
| Corregir la medición del probe | T2.12 | Validez de §6 |
| Bloques A1, A3, A4 s0/s20/s30, B, D | T2.13 (los A4 fijan `LIVE_START_GAP_S`) | D2, D10, H2, H3 |
| Prueba de audiencia | T2.13 | D6, D9 |
| Explicar el pico de lag de 1,24 s (A4-s5 t1) | T2.13 (correr con `--slow-ms` para ver callbacks lentos) | D8 |
| Prueba sostenida 2 salas × 20+ min | T2.10c / T2.10d, bloqueada por T2.1 y T2.18 | Gate de ciclo de vida |
| Gap de arranque escalonado (`LIVE_START_GAP_S`) | T2.18 (valor por T2.13) | D10 |
| Test E: 10 salas × 100 clientes (replay, en el Space) | T2.20 | D6, D9, D11 |
| Capacidad económica (billing, costo por sala-hora) | — | §2 |
