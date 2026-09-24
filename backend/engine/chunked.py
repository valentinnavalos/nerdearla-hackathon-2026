"""Fallback A: fixed audio chunks through the REST API (~480 requests per 40 min talk)."""

import io
import json
import logging
import time
import wave
from dataclasses import dataclass
from typing import AsyncIterable

from google import genai
from google.genai import types

from backend.core.events import CaptionEvent
from backend.engine.base import Emit, Engine, SessionContext
from backend.pipeline.chunker import chunk_frames
from backend.sources.base import SAMPLE_RATE, AudioFrame

LANG_NAMES = {"en": "English", "es": "neutral Spanish"}

PROMPT = (
    "You are a live interpreter for a tech conference. Transcribe the {source} audio "
    "and translate it to {target}. Keep technical terms and product names as spoken "
    "(e.g. Kubernetes, Docker, API). "
    'Reply as JSON: {{"original": "...", "translation": "..."}}. '
    'If there is no speech, return empty strings.{glossary}'
)

SCHEMA = {
    "type": "object",
    "properties": {"original": {"type": "string"}, "translation": {"type": "string"}},
    "required": ["original", "translation"],
}


@dataclass
class Result:
    original: str
    translation: str
    latency: float  # seconds spent in the request


def _wav(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def build_prompt(source_lang: str, target_lang: str, glossary: list[str] | None = None) -> str:
    g = f" Glossary (keep as-is): {', '.join(glossary)}." if glossary else ""
    return PROMPT.format(source=LANG_NAMES[source_lang], target=LANG_NAMES[target_lang], glossary=g)


class GeminiEngine:
    """One REST request per chunk: transcription + translation as JSON."""

    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    async def transcribe_translate(self, pcm: bytes, prompt: str) -> Result:
        t0 = time.monotonic()
        resp = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[prompt, types.Part.from_bytes(data=_wav(pcm), mime_type="audio/wav")],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SCHEMA,
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0),  # thinking only adds latency here
            ),
        )
        latency = time.monotonic() - t0
        data = json.loads(resp.text or "{}")
        return Result(data.get("original", ""), data.get("translation", ""), latency)


class ChunkedEngine(Engine):
    def __init__(self, api_key: str, model: str, chunk_seconds: float = 5.0, overlap_seconds: float = 0.75):
        self.api_key = api_key
        self.model = model
        self.chunk_seconds = chunk_seconds
        self.overlap_seconds = overlap_seconds

    async def run(self, frames: AsyncIterable[AudioFrame], emit: Emit, ctx: SessionContext) -> None:
        log = logging.LoggerAdapter(logging.getLogger("backend.engine"), {"session": ctx.session_id})
        gemini = GeminiEngine(self.api_key, self.model)
        prompt = build_prompt(ctx.source_lang, ctx.target_lang, ctx.glossary.terms if ctx.glossary else None)
        t_start = time.monotonic()
        seg = 0
        async for chunk in chunk_frames(frames, self.chunk_seconds, self.overlap_seconds):
            try:
                r = await gemini.transcribe_translate(chunk.pcm, prompt)
            except Exception as e:
                log.warning("chunk %d failed %s: %s", chunk.index, type(e).__name__, e)
                continue
            seg += 1
            t1 = chunk.t_capture - t_start
            lat_ms = int((time.monotonic() - chunk.t_capture) * 1000)
            tracks = ((ctx.source_lang, "orig", r.original), (ctx.target_lang, "trans", r.translation))
            for lang, kind, text in tracks:
                if not text.strip():
                    continue
                await emit(CaptionEvent(
                    session_id=ctx.session_id,
                    lang=lang,
                    kind=kind,
                    seg=seg,
                    final=True,
                    text=ctx.glossary.apply(text) if ctx.glossary else text,
                    t0=round(max(0.0, t1 - self.chunk_seconds), 3),
                    t1=round(t1, 3),
                    lat_ms=lat_ms,
                ))
