import asyncio
import logging
import time
from typing import AsyncIterable

from google.genai import types

from backend.core.dedupe import dedupe_overlap
from backend.core.events import CaptionEvent
from backend.core.segmenter import Piece, Segmenter
from backend.engine.base import Emit, Engine, SessionContext
from backend.engine.live_runner import LiveSessionRunner
from backend.sources.base import AudioFrame

TICK_S = 0.2  # how often the idle rule of the segmenters is checked
DEDUPE_TAIL_S = 2.5  # ring buffer of recently emitted text for the fresh-reconnect fallback (T2.1)


class _MeteredFrames:
    """Wraps `frames` to feed each one into SessionMetrics before yielding it.

    Must stay re-iterable like FrameQueue itself (a fresh `__aiter__()` generator per
    call): run_forever() (T2.1) re-consumes the same `frames` object across reconnects,
    and a plain async-generator function would be exhausted/closed after the first one."""

    def __init__(self, frames, ctx, now):
        self._frames = frames
        self._ctx = ctx
        self._now = now

    async def __aiter__(self):
        async for frame in self._frames:
            if self._ctx.metrics:
                self._ctx.metrics.on_frame(frame.pcm, self._now())
            yield frame


class LiveTranslateEngine(Engine):
    """Camino 1: gemini-3.5-live-translate-preview, speech-to-speech translation.
    input_transcription = original, output_transcription = translation."""

    uses_live = True

    def __init__(
        self,
        api_key: str,
        model: str,
        idle_s: float = 2.0,
        rotate_after_s: float = 540,
        max_reconnect_failures: int = 10,
        reconnect_backoffs: tuple[float, ...] = (1, 2, 4, 8, 16),
    ):
        self.api_key = api_key
        self.model = model
        self.idle_s = idle_s  # silence that closes a segment; ~1 s fragment cadence (max 2 s) per T1.4
        self.rotate_after_s = rotate_after_s
        self.max_reconnect_failures = max_reconnect_failures
        self.reconnect_backoffs = reconnect_backoffs
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
        # dedupe fallback (T2.1): the Gemini Developer API rejects `transparent=True`
        # (Vertex/Enterprise-only), so every rotation/reconnect here is a fresh connect
        # + resumption handle, not a seamless mid-stream swap - the next bit of text on
        # each track may repeat what was already emitted.
        tail = {"orig": "", "trans": ""}
        pending_dedupe = {"orig": False, "trans": False}

        def now() -> float:
            return time.monotonic() - t_start

        async def out(pieces: list[Piece], lang: str, kind: str) -> None:
            for p in pieces:
                text = p.text
                if pending_dedupe[kind] and text:
                    text = dedupe_overlap(tail[kind], text)
                    pending_dedupe[kind] = False
                if not text:
                    continue
                tail[kind] = (tail[kind] + " " + text)[-200:]
                text = ctx.glossary.apply(text) if ctx.glossary else text
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
            if ctx.metrics:
                if is_interim:
                    ctx.metrics.on_partial(now())
                else:
                    ctx.metrics.on_final(now())
            pieces = orig.preview(text, now()) if is_interim else orig.feed(text, now())
            await out(pieces, ctx.source_lang, "orig")

        async def on_output_text(text: str) -> None:
            await out(trans.feed(text, now()), ctx.target_lang, "trans")


        async def on_error(exc: Exception) -> None:
            self.callback_errors += 1
            log.error("callback error %s: %s", type(exc).__name__, exc)

        async def on_state(state: str) -> None:
            if state in ("ROTATING", "RECONNECTING"):
                pending_dedupe["orig"] = True
                pending_dedupe["trans"] = True

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
            await runner.run_forever(
                _MeteredFrames(frames, ctx, now),
                rotate_after_s=self.rotate_after_s,
                max_consecutive_failures=self.max_reconnect_failures,
                backoffs=self.reconnect_backoffs,
                on_state=on_state,
            )
        finally:
            tick_task.cancel()
            await out(orig.flush(now()), ctx.source_lang, "orig")
            await out(trans.flush(now()), ctx.target_lang, "trans")
