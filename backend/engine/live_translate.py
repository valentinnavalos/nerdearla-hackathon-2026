import time
from typing import AsyncIterator, Literal

from google.genai import types

from backend.core.events import CaptionEvent
from backend.core.glossary import Glossary
from backend.engine.base import Emit, Engine, SessionContext
from backend.engine.live_runner import LiveSessionRunner
from backend.sources.base import AudioFrame


class LiveTranslateEngine(Engine):
    """Camino 1: gemini-3.5-live-translate-preview, speech-to-speech translation.
    input_transcription = original, output_transcription = translation."""

    def __init__(
        self,
        api_key: str,
        model: str,
        source_lang: Literal["en", "es"],
        glossary: Glossary | None = None,
    ):
        self.api_key = api_key
        self.model = model
        self.source_lang: Literal["en", "es"] = source_lang
        self.target_lang: Literal["en", "es"] = "es" if source_lang == "en" else "en"
        self.glossary = glossary
        self._t_start = 0.0

    def _apply(self, text: str) -> str:
        return self.glossary.apply(text) if self.glossary else text

    async def run(self, frames: AsyncIterator[AudioFrame], emit: Emit, ctx: SessionContext) -> None:
        self._t_start = time.monotonic()
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            translation_config=types.TranslationConfig(
                target_language_code=self.target_lang,
                echo_target_language=False,
            ),
        )

        async def on_input_text(text: str, is_interim: bool) -> None:
            t0 = time.monotonic() - self._t_start
            await emit(CaptionEvent(
                session_id=ctx.session_id,
                lang=self.source_lang,
                kind="orig",
                seg=0,
                final=not is_interim,
                text=self._apply(text),
                t0=t0,
                t1=t0,
            ))

        async def on_output_text(text: str) -> None:
            t0 = time.monotonic() - self._t_start
            await emit(CaptionEvent(
                session_id=ctx.session_id,
                lang=self.target_lang,
                kind="trans",
                seg=0,
                final=True,
                text=self._apply(text),
                t0=t0,
                t1=t0,
            ))

        async def on_go_away(time_left) -> None:
            print(f"[live_translate] GoAway received, time_left={time_left}")

        async def on_error(exc: Exception) -> None:
            print(f"[live_translate] ERROR {type(exc).__name__}: {exc}")

        runner = LiveSessionRunner(
            api_key=self.api_key,
            model=self.model,
            config=config,
            on_input_text=on_input_text,
            on_output_text=on_output_text,
            on_go_away=on_go_away,
            on_error=on_error,
        )
        await runner.run(frames)
