# Alternativas de motor de transcripción y traducción

> **Qué es este documento:** alternativas al motor actual, **no implementadas**. El motor en producción es Gemini Live Translate ([`ARCHITECTURE.md` §2](../ARCHITECTURE.md#2-arquitectura-actual-implementado)). Estados según la [convención del reporte](../CONCURRENCY-REPORT.md#convención-de-estados). Las cifras marcadas DOCUMENTED vienen del proveedor o del paper citado; ninguna fue medida con nuestro audio.
>
> Última revisión: 2026-09-25 (antes: `alternativas-sesiones/OPCIONES-TRANSCRIPCION.md`).

## TL;DR

1. **Gemini Live Translate** transcribe **y** traduce en una sola sesión. Esa es su ventaja real, y su límite práctico es el cupo Live por proyecto ([reporte](../CONCURRENCY-REPORT.md)).
2. **Las APIs del navegador no son una solución offline ni universal.** Web Speech en Chrome usa un servicio en la nube y la Translator API solo corre en Chrome de escritorio. Un motor híbrido Browser/Cloud es un **EXPERIMENT**, no una decisión.
3. Los mejores modelos abiertos con streaming nativo (Nemotron 3.5 ASR Streaming, Voxtral Realtime) **necesitan GPU**. Sin GPU, la opción razonable es Parakeet TDT v3 por segmentos. Casi todos transcriben y **no traducen**.
4. Para la hackathon: mantener Gemini. Un motor alternativo solo entra si Gemini resulta ser el cuello de botella para el objetivo de salas ([roadmap](../ROADMAP.md#orden-de-trabajo), paso 10).

---

## 1. Gemini Live (motor actual y variante)

| Motor | Tipo | ¿Traduce? | Latencia | Límite práctico | Estado |
|---|---|---|---|---|---|
| **`gemini-3.5-live-translate-preview`** (actual) | Streaming nativo (nube) | ✅ EN↔ES | Original ~0,5 s (OBSERVED, T1.4, corrida única) | Cupo Live por proyecto, sin cifra publicada; conexión ~10 min y sesión de audio 15 min (DOCUMENTED) | En uso |
| `gemini-3.5-transcribe-live` | Streaming nativo (nube) | ❌ (requiere paso de traducción) | Interims + finales | Mismo cupo; acepta `custom_vocabulary` | Alternativa (Camino 2), no implementada |

## 2. Reconocimiento de voz en el navegador (Web Speech API)

| Aspecto | Qué sabemos | Estado |
|---|---|---|
| Dónde procesa | "En algunos navegadores, como Chrome, [...] el audio se envía a un servicio web para el reconocimiento, **así que no funciona offline**" | DOCUMENTED (MDN, 2026-09-25) |
| On-device | Propiedad `processLocally`: nueva y no disponible en todos los navegadores | DOCUMENTED (MDN, 2026-09-25) |
| Disponibilidad | **"Limited availability", no es Baseline**: no funciona en algunos de los navegadores más usados | DOCUMENTED (MDN, 2026-09-25) |
| Límites del servicio de Chrome | Cuotas, duración continua y cortes tras silencios: no documentados | HYPOTHESIS (a medir) |
| Vocabulario | Sin `custom_vocabulary`; el glosario se aplicaría en el servidor | HYPOTHESIS |
| Idiomas | `en` y `es` | HYPOTHESIS (verificar en el Chrome del evento) |

**Consecuencia:** no es "gratis y offline". Depende de un servicio de Google no documentado para este uso, y hay que reiniciarlo tras los silencios. Sirve como experimento para salas de menor prioridad, no como base.

## 3. Traducción en el navegador (Translator API de Chrome)

| Aspecto | Qué sabemos | Estado |
|---|---|---|
| Versión | Estable desde Chrome 138 | DOCUMENTED (Chrome for Developers, 2026-09-25) |
| Plataformas | **Solo Chrome de escritorio**, "no funciona en dispositivos móviles" | DOCUMENTED |
| Detección | `'Translator' in self` y `Translator.availability({sourceLanguage, targetLanguage})` → puede responder `'downloadable'` | DOCUMENTED |
| Modelo | Se descarga la primera vez (hay que mostrar el progreso); después corre on-device | DOCUMENTED |
| Requisitos de hardware | No detallados en la página consultada | Sin verificar |
| Idiomas | Incluye `en` y `es` | DOCUMENTED |

**Consecuencia:** sirve en la mini PC del escenario (Chrome de escritorio) y **no** en los celulares de la audiencia. Hay que implementar la detección de la función y la descarga del modelo, con un fallback.

## 4. Motores abiertos y hosteados

WER en FLEURS (habla leída, **no es audio de conferencia**): hay que probar con nuestros mp3 antes de comparar.

| Motor | Tipo | ES / EN | ¿Traduce? | WER FLEURS (es / en) | Hardware | Licencia | Estado |
|---|---|---|---|---|---|---|---|
| **Parakeet TDT 0.6B v3** | Offline, por segmentos | ✅ / ✅ | ❌ | 3,45 / 4,85 (DOCUMENTED) | **CPU viable** (ONNX int8) | CC-BY-4.0 | HYPOTHESIS: mejor opción solo CPU; latencia 1–3 s sin medir |
| **Nemotron 3.5 ASR Streaming 0.6B** | Streaming nativo | ✅ / ✅ | ❌ | — | GPU (cientos de streams por H100, DOCUMENTED) | OpenMDW-1.1 | HYPOTHESIS: mejor opción con GPU |
| **Voxtral Realtime** (~4B) | Streaming nativo | ✅ / ✅ | ❌ | — | GPU; también API paga | Apache 2.0 | HYPOTHESIS |
| **Canary 1B v2** | Offline | ✅ / ✅ | ✅ (voz → texto traducido) | 2,90 / 4,50 (DOCUMENTED) | GPU | CC-BY-4.0 | HYPOTHESIS |
| **Whisper large-v3 / turbo** | Offline; streaming con wrapper | ✅ / ✅ | Solo → inglés | 3,12 / 4,25 (DOCUMENTED) | GPU recomendada | MIT | Latencia ~3,3 s con whisper_streaming (DOCUMENTED): peor que la actual |
| **Vosk** | Streaming nativo | ✅ / ✅ | ❌ | Menor | CPU muy liviano | Apache 2.0 | Plan C, calidad baja |
| Groq Whisper (hosteado) | Por segmentos | ✅ / ✅ | ❌ | — | Nube | — | Cupo gratis a verificar (vigencia sin confirmar) |
| Workers AI Whisper turbo (hosteado) | Por segmentos | ✅ / ✅ | ❌ | — | Nube | — | ~USD 0,0005/min según el pricing relevado (vigencia sin confirmar) |

## 5. El paso de traducción (si el motor no traduce)

| Traductor | Dónde | Costo | Nota | Estado |
|---|---|---|---|---|
| Argos Translate | CPU del servidor | $0 | Stub en `backend/translate/argos_mt.py` | No implementado |
| Translator API de Chrome | Navegador de escritorio | $0 | Ver §3 | EXPERIMENT |
| m2m100-1.2B | Workers AI | Centavos | — | HYPOTHESIS |
| NLLB-200 | GPU/CPU | $0 | **CC-BY-NC (no comercial)**: evitar | Descartado |

## 6. Cómo encajaría en la arquitectura

`backend/engine/base.py` define el contrato y `factory.py` construye los motores. Un motor nuevo es un `Engine` más. **Requisito previo compartido:** elegir el motor **por sala**, porque hoy `ENGINE` es global ([`ARCHITECTURE.md`](../ARCHITECTURE.md#qué-no-está-implementado-a-la-fecha)).

| Engine nuevo | Para qué | Esfuerzo (estimación) |
|---|---|---|
| `SegmentedASREngine`: VAD → modelo offline → traductor | Parakeet, Whisper, hosteados | ~3–4 h |
| `LocalStreamingEngine`: WS contra un servidor ASR | Nemotron, Voxtral | ~4–6 h + GPU (riesgo alto) |
| Motor "browser": subtítulos hechos en la mini PC → `WS /ws/publish/{id}` | Web Speech + Translator (§2–§3) | ~3 h; **EXPERIMENT** |

## 7. Recomendación

1. **No reemplazar Gemini** mientras el objetivo sea 2 salas ([reporte](../CONCURRENCY-REPORT.md)).
2. Si hace falta un motor sin cupo Live: primero una **prueba de calidad y latencia** de ~1 h (1 min de cada mp3 por Gemini, Parakeet y Whisper turbo contra una transcripción manual) y recién después decidir.
3. El motor browser queda como EXPERIMENT, con feature detection y fallback, nunca como única vía.

## Fuentes (consultadas el 2026-09-25 salvo indicación)

- MDN, SpeechRecognition: https://developer.mozilla.org/docs/Web/API/SpeechRecognition
- Chrome for Developers, Translator API: https://developer.chrome.com/docs/ai/translator-api
- Gemini Live API, session management: https://ai.google.dev/gemini-api/docs/live-api/session-management
- Parakeet TDT 0.6B v3: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 · paper (WER): https://arxiv.org/pdf/2509.14128
- Nemotron 3.5 ASR Streaming: https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b
- Voxtral: https://mistral.ai/news/voxtral-transcribe-2 · whisper_streaming: https://github.com/ufal/whisper_streaming
- Groq Whisper: https://console.groq.com/docs/model/whisper-large-v3-turbo · Workers AI pricing: https://developers.cloudflare.com/workers-ai/platform/pricing/ (relevados en la versión anterior, sin reverificar)
