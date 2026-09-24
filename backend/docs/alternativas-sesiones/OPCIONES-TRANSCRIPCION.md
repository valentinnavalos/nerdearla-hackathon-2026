# Motores de transcripción alternativos: Whisper, Parakeet, Nemotron, Voxtral y otros

> Complementa a `OPCIONES-ESCALADO.md` (opción E, "100% local").
> Convención: **Documentado** = lo dice el proveedor o el paper · **Hipótesis** = estimación nuestra, sin medir · **NO VERIFICADO** = no se pudo confirmar en una fuente oficial.

---

## TL;DR

1. **Los mejores modelos abiertos de 2026 ya son streaming nativo y multilingües** (Nemotron 3.5 ASR Streaming, Voxtral Realtime): calidad cercana a lo offline con latencias sub-segundo. **Pero necesitan GPU**, y no hay hosting gratis con GPU apto para streams continuos de 40 min.
2. **Whisper no es streaming.** Los wrappers de streaming (whisper_streaming) reportan ~3,3 s de latencia con GPU: igual o peor que lo que ya tenemos con Gemini.
3. **Parakeet TDT 0.6B v3** es la mejor opción **solo CPU** con español e inglés (CC-BY-4.0, versiones ONNX int8 para CPU), pero es un modelo offline: hay que segmentar el audio por pausas.
4. **Casi todos hacen solo transcripción.** Para EN→ES hace falta un paso de traducción aparte (Argos, m2m100, Translator de Chrome o un LLM). Gemini live-translate resuelve las dos cosas en una sola sesión: esa es su ventaja real.
5. **Opción paga más barata para producción:** Whisper turbo en Cloudflare Workers AI a USD 0,0005 por minuto de audio (~USD 0,03 por hora por sala), que encaja con la idea de Durable Objects.
6. **Para la hackathon:** mantener Gemini como motor principal. Si sobra tiempo, sumar **un** motor abierto como plugin del `Engine` para mostrar "sin dependencia de un proveedor". La elección depende de si tenemos GPU (sección 6).

---

## 1. Qué evaluamos

| Criterio | Por qué importa |
|---|---|
| **Streaming nativo vs. por segmentos** | Define la latencia: nativo = parciales en < 1 s; por segmentos = esperar a que termine la frase |
| **Español + inglés** | Requisito mínimo del desafío |
| **¿Traduce?** | Si no, hay que sumar un paso de traducción (más latencia y otra pieza) |
| **Calidad** | WER en FLEURS (habla leída; **no es audio de conferencia**, hay que probar con nuestros mp3) |
| **Hardware** | HF gratis = 2 vCPU sin GPU |
| **Licencia** | El proyecto es open source; algunas licencias de modelos prohíben uso comercial |
| **Costo** | Objetivo: cero |

---

## 2. Tabla comparativa principal

| Motor | Tipo | ES / EN | ¿Traduce? | WER FLEURS (es / en) | Latencia | Hardware | Licencia | Veredicto |
|---|---|---|---|---|---|---|---|---|
| **Gemini Live Translate** (actual) | Streaming nativo (nube) | ✅ / ✅ | ✅ EN↔ES | No publicado | ~0,5 s el original (observado, T1.4) | Nube | Términos de Google | ✅ Principal; límite: cupo free (2 salas) |
| **Gemini Transcribe Live** | Streaming nativo (nube) | ✅ / ✅ | ❌ | No publicado | Parciales + finales | Nube | Términos de Google | Alternativa con `custom_vocabulary` |
| **Whisper large-v3 / turbo** (faster-whisper, whisper.cpp) | Offline; streaming con wrapper | ✅ / ✅ | Solo → inglés | 3,12 / 4,25 (large-v3, documentado) | ~3,3 s con whisper_streaming (documentado, con GPU) | GPU recomendada; CPU lento con modelos grandes | MIT | ⚠️ Buena calidad, latencia alta |
| **SimulStreaming** (Whisper + EuroLLM) | Política de streaming | ✅ / ✅ | ✅ (LLM, admite terminología) | — | ~5× más rápido que whisper_streaming (documentado) | 1–2 GPU | **NO VERIFICADO** | Interesante para traducción, pesado |
| **Parakeet TDT 0.6B v3** | Offline (se usa por segmentos) | ✅ / ✅ (25 idiomas europeos) | ❌ | 3,45 / 4,85 (documentado) | Fin de frase + inferencia (hipótesis: 1–3 s) | **CPU viable** (ONNX int8) | CC-BY-4.0 | ✅ **Mejor opción solo CPU** |
| **Canary 1B v2** | Offline | ✅ / ✅ (25 idiomas) | ✅ (traducción de voz) | 2,90 / 4,50 (documentado) | Por segmentos | GPU | CC-BY-4.0 | Buena calidad + traduce; requiere GPU |
| **Nemotron 3.5 ASR Streaming 0.6B** (jun. 2026) | **Streaming nativo** (cache-aware) | ✅ / ✅ (40 locales) | ❌ | — | Chunk configurable de 80 ms a 1,12 s | GPU (240–2400 streams por H100, documentado); CPU **NO VERIFICADO** | OpenMDW-1.1 | ✅ **Mejor opción con GPU** |
| **Voxtral Realtime** (Mistral, ~4B) | **Streaming nativo** | ✅ / ✅ (13 idiomas) | ❌ | Con 2,4 s de delay iguala al modelo batch (documentado) | Configurable hasta < 200 ms | GPU | Apache 2.0 | ✅ Excelente con GPU; también API paga barata |
| **Moonshine Streaming** (34M–245M) | Streaming nativo | Inglés (español en streaming: **NO VERIFICADO**) | ❌ | — | Sub-segundo (edge) | CPU / edge | **VERIFICAR** | Solo para charlas en inglés |
| **Vosk** (Kaldi) | Streaming nativo | ✅ / ✅ | ❌ | Menor que los anteriores | Baja | CPU muy liviano | Apache 2.0 | Plan C barato; calidad baja |
| **Web Speech API** (Chrome) | Streaming (nube de Google o on-device experimental) | ✅ / ✅ | ❌ (se suma Translator de Chrome) | — | Baja | Navegador | Función del navegador | Ya propuesto como motor "browser" |

**Nota sobre la calidad:** los WER vienen del paper de NVIDIA sobre FLEURS. Gemini no aparece en esa tabla, y FLEURS es habla leída. La comparación que importa es con **nuestros mp3** (ver sección 7).

---

## 3. Servicios hosteados (sin GPU propia)

| Servicio | Modelo | Tipo | Gratis | Pago | Encaje |
|---|---|---|---|---|---|
| **Groq** | Whisper large-v3 / turbo | Por segmentos (archivos) | 20 RPM, 2.000 req/día, 7.200 s de audio/hora, 28.800 s/día (**VERIFICAR VIGENCIA**) | USD 0,04/h (turbo); se factura mínimo 10 s por request | Gratis alcanza para 1–2 salas: con segmentos de 5 s, cada sala hace ~12 RPM |
| **Cloudflare Workers AI** | Whisper large-v3 turbo | Por segmentos | 10.000 neuronas/día ≈ **214 min de audio/día** | USD 0,0005/min ≈ **USD 0,03/h por sala** | ✅ Encaja con Durable Objects: todo queda en Cloudflare |
| **Cloudflare Workers AI** | Deepgram Nova-3 (WebSocket) | **Streaming** | ≈ 12 min/día | USD 0,0092/min ≈ USD 0,55/h por sala | Streaming real, pago |
| **Cloudflare Workers AI** | m2m100-1.2B (traducción) | Texto | Comparte las 10.000 neuronas/día | USD 0,342 por millón de tokens | Paso de traducción barato en el edge |
| **Mistral API** | Voxtral Realtime | Streaming | **NO VERIFICADO** | USD 0,006/min ≈ USD 0,36/h por sala | Streaming abierto, barato |

### Costo de 10 salas × 40 min (6,7 h de audio), opciones pagas

| Opción | Costo aprox. | Nota |
|---|---|---|
| Workers AI Whisper turbo | ~USD 0,20 | Por segmentos; + traducción |
| Groq Whisper turbo | ~USD 0,27–0,53 | Depende del mínimo facturado de 10 s |
| Voxtral Realtime (API) | ~USD 2,40 | Streaming nativo; + traducción |
| Workers AI Nova-3 (WebSocket) | ~USD 3,70 | Streaming nativo; + traducción |
| Gemini Live Translate | ~USD 14,70 | Transcribe **y** traduce en una sesión (pricing relevado; **VERIFICAR VIGENCIA**) |

---

## 4. El paso de traducción (si el motor no traduce)

| Traductor | Dónde corre | Costo | Calidad | Licencia | Nota |
|---|---|---|---|---|---|
| **Argos Translate** (modelos OPUS) | CPU del servidor | $0 | Media | MIT (librería) | Stub ya creado en `backend/translate/argos_mt.py` |
| **Translator API de Chrome** | Navegador de la mini PC | $0 | Buena | Función del navegador | Solo escritorio; va con el motor "browser" |
| **m2m100-1.2B** | Workers AI | Centavos | Media-buena | MIT | Encaja con Cloudflare |
| **Canary 1B v2** | GPU | $0 de API | Buena | CC-BY-4.0 | Traduce directo desde la voz (sin paso de texto) |
| **EuroLLM** (vía SimulStreaming) | GPU | $0 de API | Buena, admite terminología | **NO VERIFICADO** | Pesado (9B) |
| **Gemini texto** (Flash-Lite) | Nube | Free tier con pocas requests/día | Muy buena | Términos de Google | No escala en free tier (lo vimos en el plan) |
| **NLLB-200** | GPU/CPU | $0 | Buena | **CC-BY-NC (no comercial)** | ⚠️ Evitar: limita a conferencias con fines comerciales |

---

## 5. Hardware: dónde correría cada opción

| Dónde | Qué entra | Capacidad (hipótesis, a medir) |
|---|---|---|
| **HF Space gratis** (2 vCPU, 16 GB, sin GPU) | Parakeet v3 ONNX int8, Moonshine (EN), Vosk, Argos | Parakeet: ~1–2 salas; Vosk: más salas con menos calidad |
| **PC con GPU en el evento** (ej. RTX de 12 GB) | Nemotron 3.5, Voxtral Realtime, Canary, Whisper turbo | Nemotron: 10 salas en una GPU es plausible (documentado: cientos de streams en H100) |
| **GPU en la nube** | Todo | Pago; fuera del objetivo de costo cero |
| **GPU gratis** (Colab, Kaggle, ZeroGPU) | — | No aptos para servir streams continuos de 40 min (**NO VERIFICADO** en detalle) |

**Patrón de despliegue para GPU local:** `docker compose --profile gpu up` en una PC del evento más el túnel de Cloudflare que ya está en el plan (T3.10). El backend es el mismo; solo cambia el engine.

---

## 6. Cómo encaja en nuestra arquitectura

El código ya está preparado para agregar motores: `backend/engine/base.py` define la interfaz y `factory.py` los construye. Hay que agregar:

| Engine nuevo | Para qué modelos | Esfuerzo |
|---|---|---|
| `SegmentedASREngine`: VAD (corte por pausas) → modelo offline → traductor | Parakeet, Whisper, Groq, Workers AI | ~3–4 h (VAD + modelo + Argos + tests) |
| `LocalStreamingEngine`: WebSocket contra un servidor de ASR streaming | Nemotron (NeMo/Riva), Voxtral | ~4–6 h + setup de GPU (riesgo alto en 15 h) |
| Traductor enchufable (`translate/`) | Argos, m2m100 | ~1 h (Argos ya tiene el archivo creado) |

Requisito compartido con el motor híbrido: **elegir el engine por sala**, porque hoy `factory.py` usa un único `ENGINE` global.

---

## 7. Recomendación

**Para la hackathon (tiempo limitado):**
1. **No reemplazar Gemini.** Primero los P0 de Fase 2 y el motor híbrido (`OPCIONES-ESCALADO.md`).
2. Si sobra tiempo, sumar **un** motor abierto como plugin:
   - **Sin GPU → Parakeet TDT v3 (ONNX int8) + Argos**, dentro del mismo container de HF. Muestra "funciona sin Google y sin costo". Latencia por segmentos: medirla.
   - **Con una GPU NVIDIA a mano → Nemotron 3.5 ASR Streaming + Argos.** Es la mejor historia técnica (streaming nativo, 40 idiomas, cientos de streams por GPU), pero el setup de NeMo es un riesgo real con el tiempo que queda.
3. **Prueba rápida antes de decidir (~1 h):** pasar 1 minuto de cada mp3 por Gemini, Parakeet y Whisper turbo; comparar contra una transcripción manual (WER aproximado) y medir la latencia hasta el final de cada frase.

**Para el README (roadmap de producción):**
- **Modo local:** Nemotron o Voxtral en una GPU del evento → costo de API cero, escala a 10+ salas por GPU.
- **Modo edge económico:** Workers AI (Whisper turbo + m2m100) + Durable Objects → ~USD 0,03/h por sala, todo en Cloudflare.
- **Modo premium:** Gemini Live Translate con billing → mejor calidad de traducción, ~USD 2,2/h por sala.

---

## Fuentes

- Parakeet TDT 0.6B v3 (model card): https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- Paper Canary-1B-v2 & Parakeet-TDT-0.6B-v3 (WER por idioma): https://arxiv.org/pdf/2509.14128
- Nemotron 3.5 ASR Streaming 0.6B: https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b
- NVIDIA NeMo Speech (novedades 2026): https://github.com/NVIDIA-NeMo/Speech
- Voxtral Transcribe 2 / Voxtral Realtime: https://mistral.ai/news/voxtral-transcribe-2
- whisper_streaming (latencia 3,3 s): https://github.com/ufal/whisper_streaming
- SimulStreaming: https://github.com/ufal/SimulStreaming
- Moonshine Streaming: https://huggingface.co/UsefulSensors/moonshine-streaming-tiny
- Groq Whisper (modelo y precio): https://console.groq.com/docs/model/whisper-large-v3-turbo
- Cloudflare Workers AI pricing: https://developers.cloudflare.com/workers-ai/platform/pricing/
