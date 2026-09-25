# Opciones de arquitectura para escalar a 10 salas concurrentes

> Basado en la rama `roadmap` (commit `9b02636`), en las mediciones de `TASKS.md` y en la documentación oficial de Google y Cloudflare (ver Fuentes).
> Convención: **Observado** = lo midieron ustedes · **Documentado** = lo dice el proveedor · **NO VERIFICADO** = no se pudo confirmar en una fuente oficial.

---

## TL;DR

1. "Escalar a 10 salas" son **dos problemas distintos**:
  - **Cuántas salas Live** pueden correr a la vez → lo limita el **cupo de Gemini** por proyecto.
  - **Cuántos oyentes** reciben subtítulos → lo limita la **capa de distribución** (WebSockets).
2. **Ninguna opción de hosting resuelve el cupo de Gemini.** Cloudflare, HF u Oracle abren la misma cantidad de sesiones Live, porque el límite es por proyecto de Google.
3. **Cloudflare Durable Objects sí sirve**, como **capa de distribución a la audiencia** (miles de oyentes, gratis), **sin reescribir el motor**: el motor sigue en Python en HF y publica los subtítulos a Cloudflare.
4. Para llegar a **10 salas a costo cero**: motor por sala (Gemini Live en las salas prioritarias + motor en el navegador en el resto). Para **10 salas Live**: activar billing.

---



## 1. Los dos cuellos de botella


| Dimensión                  | Límite hoy                                                    | Evidencia                                                           | Qué lo resuelve                                                          |
| -------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **Salas Live simultáneas** | 2 estables en free tier; abrir sesiones seguidas degrada 3–7× | Observado (T2.10a). Google no publica el límite: **NO DETERMINADO** | Motor por sala (sección 3, opción D) o billing (opción C)                |
| **Oyentes por sala**       | Sin medir                                                     | El fan-out actual serializa JSON una vez por cliente (sección 2)    | Fixes chicos en el backend y, si hace falta, Durable Objects (sección 4) |
| Audio de entrada           | 10 × 32 KB/s ≈ 2,6 Mbps                                       | Cálculo                                                             | No es problema                                                           |
| Disco                      | Escritor asíncrono por sala                                   | Observado (test con disco lento)                                    | Ya resuelto                                                              |
| CPU del motor              | Callbacks ≤ 1,4 ms, 0 frames perdidos con 2 salas             | Observado; con 10 salas es hipótesis                                | Test E (sección 6)                                                       |


---



## 2. Evidencia del código (rama `roadmap`)


| Archivo                            | Qué hace                                                                | Implicancia para 10 salas                                                                                                                     |
| ---------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/core/manager.py` L86–104  | Guardia de capacidad: chequea y reserva el cupo sin `await` en el medio | ✅ Sin condición de carrera (un solo event loop). La 3ª sala Live recibe `CapacityError`                                                       |
| `backend/engine/factory.py`        | `create_engine(settings)` usa **un solo** `ENGINE` **global**           | ⚠️ Para el motor por sala, el engine tiene que elegirse **por sala** (`create_engine(settings, name)`)                                        |
| `backend/core/session.py` L204     | `event.model_dump()` una vez por evento                                 | ✅ Bien                                                                                                                                        |
| `backend/api/ws.py` L60            | `ws.send_json(...)` por cliente                                         | ⚠️ `json.dumps` se repite **una vez por oyente** por evento. Con 10 salas × 100 oyentes × ~8 eventos/s son ~8.000 serializaciones/s evitables |
| `backend/core/session.py` L222–226 | Cola por cliente; si está llena, descarta el más viejo                  | ✅ Un cliente lento no bloquea la sala                                                                                                         |
| `backend/api/ws.py` L48–63         | 2 tareas por cliente (lector + escritor)                                | OK hasta miles de clientes; costo de memoria lineal                                                                                           |


---



## 3. Tabla comparativa A — Motor (cuántas salas Live)


| Opción                                                                                    | Salas simultáneas            | Costo                                                          | Calidad                          | Cambio de código                       | Riesgo principal                                                                       | Veredicto                       |
| ----------------------------------------------------------------------------------------- | ---------------------------- | -------------------------------------------------------------- | -------------------------------- | -------------------------------------- | -------------------------------------------------------------------------------------- | ------------------------------- |
| **A.** Todo Gemini Live, 1 proyecto free (actual)                                         | 2                            | $0                                                             | Alta                             | —                                      | Degradación al abrir sesiones seguidas                                                 | Base actual                     |
| **B.** Pool de keys de varios proyectos                                                   | 10                           | $0                                                             | Alta                             | Bajo                                   | **Viola los términos de Google** (prohíben eludir límites; pueden suspender sin aviso) | ❌ Descartada                    |
| **C.** Todo Gemini Live con billing                                                       | 10 (cupo Tier 1 a confirmar) | ~USD 2,2/h por sala (pricing relevado; **VERIFICAR VIGENCIA**) | Alta                             | Casi nulo (solo `MAX_CONCURRENT_LIVE`) | Costo                                                                                  | ✅ Opción de producción          |
| **D.** **Motor por sala (híbrido)**: Gemini Live en N salas + motor navegador en el resto | 10+                          | $0                                                             | Alta en Live, media en navegador | Medio (~3 h)                           | Calidad desigual; APIs del navegador con límites no documentados                       | ✅ **Recomendada para $0**       |
| **E.** Motor abierto (Parakeet, Nemotron, Voxtral, Whisper…)                              | Según hardware               | $0 de API (o centavos hosteado)                                | Media-alta                       | Medio-alto                             | Streaming nativo requiere GPU                                                          | Ver `OPCIONES-TRANSCRIPCION.md` |


**Motor navegador (opción D), en detalle:**

- **Transcripción:** Web Speech API de Chrome (`continuous` + `interimResults`). En Chrome usa un servicio de Google en la nube, gratis y sin API key. El modo on-device (`processLocally`) es experimental.
- **Traducción:** Translator API de Chrome, estable desde la v138, on-device, solo escritorio, incluye `en` y `es`.
- Corre en la **mini PC del escenario**; manda subtítulos ya hechos al servidor por `WS /ws/publish/{id}`. **No ocupa cupo Live.**
- Política sugerida: **Live para charlas en inglés** (la traducción EN→ES es el núcleo del desafío), **navegador para charlas en español**.
- Limitaciones: sin `custom_vocabulary` (el glosario se aplica igual en el servidor); se corta tras silencios y hay que reiniciarlo; usa la entrada de audio por defecto del sistema; requiere Chrome de escritorio.

---



## 4. Tabla comparativa B — Distribución y hosting (cuántos oyentes)


| Opción                                                          | Qué corre dónde                                        | Oyentes (WebSockets)                                                            | Límites del plan gratis                                                                 | Sleep / cold start           | Reescritura                                                        | Veredicto                                                    |
| --------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------ |
| **B1.** Solo HF Space (actual)                                  | Todo en un container Python                            | **NO DETERMINADO** (medir con test E)                                           | 2 vCPU / 16 GB; límites de red **NO VERIFICADO**                                        | Se duerme sin tráfico        | —                                                                  | ✅ Suficiente para la demo                                    |
| **B2.** **HF (motor) + Cloudflare Durable Objects (audiencia)** | Motor en HF; 1 Durable Object por sala hace el fan-out | Hasta 32.768 WS por DO (documentado; el límite práctico depende de CPU/memoria) | 100.000 requests/día y 13.000 GB-s/día; si se supera, las operaciones fallan (no cobra) | DO se crea al primer request | ~150 líneas TS nuevas; el motor no se toca                         | ✅ **Viable y valiosa** para audiencias grandes               |
| **B3.** Todo en Cloudflare (motor en un DO)                     | Motor portado a TS dentro del DO                       | Igual que B2                                                                    | Igual que B2, pero la conexión a Gemini **no hiberna** → duración continua              | Igual que B2                 | Portar ~800 líneas (runner, engine, segmenter, glosario, sesiones) | ❌ No ahora: mucho esfuerzo y **no mejora el cupo de Gemini** |
| **B4.** Oracle Cloud Always Free                                | Todo en una VM ARM                                     | Más CPU que HF                                                                  | **VERIFICAR VIGENCIA**                                                                  | No duerme                    | — (Docker igual)                                                   | Alternativa de producción; operación manual                  |
| **B5.** Google Cloud Run                                        | Container con autoscaling                              | Bueno                                                                           | Exige billing                                                                           | Cold start                   | Sticky sessions (estado en memoria)                                | ❌ Descartada (costo cero + estado)                           |
| **B6.** Render / Fly.io free                                    | Container                                              | Bajo                                                                            | CPU mínima / sin free tier para cuentas nuevas (**NO VERIFICADO**)                      | Render duerme rápido         | —                                                                  | ❌ Descartada                                                 |


---



## 5. Zoom: Cloudflare Durable Objects (opción B2)



### Por qué encaja

- Un **Durable Object (DO)** es una instancia única con estado, direccionable por nombre → **un DO por sala** (`sala-1`, `sala-2`…).
- Con la **WebSocket Hibernation API**, las conexiones inactivas **no generan costo de duración**: solo se cobra el tiempo en que se ejecuta código.
- Los **mensajes salientes** (del DO a los oyentes) **no se cobran**; los entrantes se cuentan 20:1.
- Los assets estáticos (la página de audiencia) en Workers son **gratis e ilimitados**.
- Separa planos: el HF Space queda para operador, mini PCs y motor; la audiencia pública (miles de conexiones) va contra el edge de Cloudflare.



### Cómo quedaría

```
PLANO DE CONTROL Y MOTOR (HF Space, Python — sin cambios)        PLANO DE AUDIENCIA (Cloudflare, gratis)

Mini PC ──audio WS──► FastAPI ──WSS──► Gemini Live
                        │
                        │ CaptionEvent (1 WS por sala, con token)
                        └──────────────────────────────► Worker ──► DO "sala-1" ──► celulares / OBS (miles)
                                                                 ├─► DO "sala-2" ──► ...
                                                                 └─► DO "sala-N"
Consola de operador y vista de escenario → HF          Página de audiencia (estática) → Cloudflare
```



### Números para 10 salas en el plan gratis

Supuestos: ~8 eventos/s por sala (observado en T1.3/T2.10a), charla de 40 min, 4 turnos por día.


| Concepto                                 | Cálculo                                 | Resultado                                                                  |
| ---------------------------------------- | --------------------------------------- | -------------------------------------------------------------------------- |
| Mensajes entrantes al DO por sala-charla | 8/s × 2.400 s = 19.200 → ÷20            | **~960 requests** (~480 si se limitan los interim a 4/s)                   |
| Conexiones de oyentes                    | 1 request por conexión (+ reconexiones) | 200 oyentes → ~200 requests                                                |
| Día con 10 salas × 4 turnos              | 40 × (960 + 200)                        | **~46.000 requests/día** (límite: 100.000)                                 |
| Duración, peor caso (DO siempre activo)  | 0,128 GB × 2.400 s                      | ~307 GB-s por sala-charla → **~42 sala-charlas/día** (límite: 13.000 GB-s) |
| Duración, caso real (con hibernación)    | Solo el tiempo de los handlers          | Muy por debajo del peor caso                                               |


**Cuidados de diseño:**

- **Historial para quien entra tarde:** al hibernar, el DO pierde la memoria. Guardar los últimos finales en el storage del DO (cuidado: ~1.300 escrituras por sala-charla; límite gratis 100.000 filas/día) o aceptar que sin actividad reciente no haya historial.
- **Ubicación:** el DO se crea cerca del primer request (el HF Space, en EE. UU./Europa). Usar `locationHint` de Sudamérica (**VERIFICAR VIGENCIA**) si la latencia importa.
- **CPU por invocación:** Workers Free tiene 10 ms por invocación; el límite exacto para DO en plan Free queda **NO VERIFICADO**. Mitigación: serializar una vez y mandar el mismo string a todos.
- **Fallback:** si se supera un límite gratis, las operaciones fallan. La página de audiencia tiene que poder volver a conectarse directo al WS de HF.



### Esfuerzo estimado (~3 h)


| Pieza                                                                                                        | Dónde           | Líneas aprox. |
| ------------------------------------------------------------------------------------------------------------ | --------------- | ------------- |
| Worker + DO: `/publish/{sala}` (con token) y `/ws/{sala}?lang=` (audiencia), broadcast por idioma, historial | Cloudflare (TS) | ~120–150      |
| `CloudflarePublisher`: por sala, abre un WS al DO y reenvía cada `CaptionEvent` (con reconexión)             | HF (Python)     | ~60           |
| Página de audiencia: URL del WS configurable (HF o Cloudflare) con fallback                                  | Frontend        | ~20           |
| Test de carga contra el DO                                                                                   | Script          | ~40           |




### Por qué no B3 (todo en Cloudflare)

- Las conexiones **salientes** de un DO (la de Gemini) **no hibernan** → duración cobrada todo el tiempo de la charla.
- Hay que portar a TS todo lo que ya anda y tiene tests (`live_runner`, `live_translate`, `segmenter`, `glossary`, `session`, `manager`).
- **No agrega ni una sesión Live más:** el cupo de Gemini sigue siendo el mismo.
- Python en Workers soporta DO, pero que `google-genai` funcione ahí queda **NO VERIFICADO**.

---



## 6. Escenarios recomendados


| Escenario                                | Motor                    | Distribución | Salas   | Oyentes          | Costo                                            | Esfuerzo extra |
| ---------------------------------------- | ------------------------ | ------------ | ------- | ---------------- | ------------------------------------------------ | -------------- |
| **E1.** Demo mínima (hoy)                | A                        | B1           | 2       | A medir          | $0                                               | —              |
| **E2.** 10 salas a $0                    | D (2 Live + 8 navegador) | B1 + fixes   | 10      | A medir (test E) | $0                                               | ~3,5 h         |
| **E3.** 10 salas a $0 + audiencia masiva | D                        | **B2**       | 10      | Miles            | $0                                               | ~6,5 h         |
| **E4.** Producción Nerdearla             | C (billing)              | **B2**       | 10 Live | Miles            | ~USD 2,2/h por sala (Gemini) + Cloudflare gratis | ~3 h (B2)      |


**Fixes del backend incluidos en E2–E4 (~45 min):**

1. **Serializar una sola vez por evento** (`json.dumps` en `emit`, `send_text` en `ws.py`).
2. **Limitar los interim** a ≤ 4/s por sala e idioma (mandar solo el último).
3. **Arranque escalonado:** 20–30 s mínimo entre sesiones Live nuevas (las reanudaciones no cuentan).
4. **Engine por sala** en `factory.py` (requisito de D).

---



## 7. Recomendación y orden de trabajo

1. **Terminar los P0 de Fase 2**: T2.1 (rotación con reanudación), T2.5–T2.9, T2.10c (2 salas × 20 min).
2. **Fixes del backend** (sección 6).
3. **Test E**: 10 salas en `replay` × 100 clientes WS cada una, en el Space. Mide el fan-out **sin gastar cupo de Gemini** y decide si B2 es necesario ya o queda como roadmap.
4. **Motor por sala (D)** → 10 salas a $0.
5. **Durable Objects (B2)** si el test E muestra límites, o si queda tiempo: es el argumento más fuerte de escalabilidad para el jurado ("la audiencia escala en el edge, gratis").
6. Documentar **E4** en el README como camino de producción.



## 8. Para decidir entre los dos

- ¿Cuántos oyentes esperamos por sala (presencial + remoto)? Define si B2 entra en la demo o queda como roadmap.
- ¿Cuántas horas quedan después de cerrar los P0?
- ¿Alguno se siente cómodo con TypeScript para el Worker/DO (~150 líneas)?

---



## Fuentes

- Google APIs Terms of Service (sección *API Limitations*): [https://developers.google.com/terms](https://developers.google.com/terms)
- Gemini API Additional Terms of Service: [https://ai.google.dev/gemini-api/terms](https://ai.google.dev/gemini-api/terms)
- Gemini API — Rate limits (por proyecto): [https://ai.google.dev/gemini-api/docs/rate-limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- Gemini Live API — Session management: [https://ai.google.dev/gemini-api/docs/live-api/session-management](https://ai.google.dev/gemini-api/docs/live-api/session-management)
- Cloudflare Durable Objects — Pricing: [https://developers.cloudflare.com/durable-objects/platform/pricing](https://developers.cloudflare.com/durable-objects/platform/pricing)
- Cloudflare Durable Objects — WebSockets / Hibernation: [https://developers.cloudflare.com/durable-objects/best-practices/websockets/](https://developers.cloudflare.com/durable-objects/best-practices/websockets/)
- Cloudflare Workers — Pricing: [https://developers.cloudflare.com/workers/platform/pricing/](https://developers.cloudflare.com/workers/platform/pricing/)
- Chrome Translator API: [https://developer.chrome.com/docs/ai/translator-api](https://developer.chrome.com/docs/ai/translator-api)
- Web Speech API (MDN): [https://developer.mozilla.org/docs/Web/API/SpeechRecognition](https://developer.mozilla.org/docs/Web/API/SpeechRecognition)

