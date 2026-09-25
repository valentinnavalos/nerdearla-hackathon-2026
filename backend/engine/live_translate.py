import asyncio
import logging
import time
from typing import AsyncIterable

from google.genai import types

from backend.core.events import CaptionEvent
from backend.core.segmenter import Piece, Segmenter
from backend.engine.base import Emit, Engine, SessionContext
from backend.engine.live_runner import LiveSessionRunner
from backend.sources.base import AudioFrame

TICK_S = 0.2  # how often the idle rule of the segmenters is checked


class LiveTranslateEngine(Engine):
    """Camino 1: gemini-3.5-live-translate-preview, speech-to-speech translation.
    input_transcription = original, output_transcription = translation."""

    uses_live = True

    def __init__(self, api_key: str, model: str, idle_s: float = 2.0):
        self.api_key = api_key
        self.model = model
        self.idle_s = idle_s  # silence that closes a segment; ~1 s fragment cadence (max 2 s) per T1.4
        self.runner: LiveSessionRunner | None = None  # exposes runner.stats (T2.4)
        self.callback_errors = 0

    @staticmethod
    def build_config(target_lang: str) -> types.LiveConnectConfig:
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            translation_config=types.TranslationConfig(
                target_language_code=target_lang,
                echo_target_language=False,
            ),
        )

    async def run(self, frames: AsyncIterable[AudioFrame], emit: Emit, ctx: SessionContext) -> None:
        log = logging.LoggerAdapter(logging.getLogger("backend.engine"), {"session": ctx.session_id})
        t_start = time.monotonic()
        orig, trans = Segmenter(idle_s=self.idle_s), Segmenter(idle_s=self.idle_s)

        def now() -> float:
            return time.monotonic() - t_start

        async def out(pieces: list[Piece], lang: str, kind: str) -> None:
            for p in pieces:
                text = ctx.glossary.apply(p.text) if ctx.glossary else p.text
                await emit(CaptionEvent(
                    session_id=ctx.session_id,
                    lang=lang,
                    kind=kind,
                    seg=p.seg,
                    final=p.final,
                    text=text,
                    t0=round(p.t0, 3),
                    t1=round(p.t1, 3),
                ))

        async def on_input_text(text: str, is_interim: bool) -> None:
            pieces = orig.preview(text, now()) if is_interim else orig.feed(text, now())
            await out(pieces, ctx.source_lang, "orig")

        async def on_output_text(text: str) -> None:
            await out(trans.feed(text, now()), ctx.target_lang, "trans")

        async def on_error(exc: Exception) -> None:
            self.callback_errors += 1
            log.error("callback error %s: %s", type(exc).__name__, exc)

        async def ticker() -> None:
            while True:
                await asyncio.sleep(TICK_S)
                await out(orig.tick(now()), ctx.source_lang, "orig")
                await out(trans.tick(now()), ctx.target_lang, "trans")

        runner = self.runner = LiveSessionRunner(
            api_key=self.api_key,
            model=self.model,
            config=self.build_config(ctx.target_lang),
            on_input_text=on_input_text,
            on_output_text=on_output_text,
            on_error=on_error,
            log=log,
        )
        tick_task = asyncio.create_task(ticker())
        try:
            await runner.run(frames)
        finally:
            tick_task.cancel()
            await out(orig.flush(now()), ctx.source_lang, "orig")
            await out(trans.flush(now()), ctx.target_lang, "trans")
