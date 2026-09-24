import io
import json
import time
import wave
from dataclasses import dataclass

from google import genai
from google.genai import types

from backend.sources.base import SAMPLE_RATE

PROMPT = (
    "You are a live interpreter for a tech conference. Transcribe the English audio "
    "and translate it to Spanish (Rioplatense, neutral tone). Keep technical terms and "
    "product names in English (e.g. Kubernetes, Docker, API). "
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


class GeminiEngine:
    def __init__(self, api_key: str, model: str, glossary: list[str] | None = None):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        g = f" Glossary (keep as-is): {', '.join(glossary)}." if glossary else ""
        self.prompt = PROMPT.format(glossary=g)

    async def transcribe_translate(self, pcm: bytes) -> Result:
        t0 = time.monotonic()
        resp = await self.client.aio.models.generate_content(
            model=self.model,
            contents=[
                self.prompt,
                types.Part.from_bytes(data=_wav(pcm), mime_type="audio/wav"),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=SCHEMA,
                temperature=0.2,
            ),
        )
        latency = time.monotonic() - t0
        data = json.loads(resp.text or "{}")
        return Result(data.get("original", ""), data.get("translation", ""), latency)
