import asyncio
from typing import AsyncIterator, Awaitable, Callable

from google import genai
from google.genai import types

from backend.sources.base import AudioFrame

OnInputText = Callable[[str, bool], Awaitable[None]]  # (text, is_interim)
OnOutputText = Callable[[str], Awaitable[None]]
OnAudio = Callable[[bytes], Awaitable[None]]  # pcm24k, unused for now
OnGoAway = Callable[[float | None], Awaitable[None]]
OnError = Callable[[Exception], Awaitable[None]]


class LiveSessionRunner:
    """Owns one Gemini Live (bidiGenerateContent) session: sends audio frames,
    dispatches received messages to callbacks. No rotation/reconnect logic here."""

    def __init__(
        self,
        api_key: str,
        model: str,
        config: types.LiveConnectConfig,
        on_input_text: OnInputText,
        on_output_text: OnOutputText | None = None,
        on_audio: OnAudio | None = None,
        on_go_away: OnGoAway | None = None,
        on_error: OnError | None = None,
    ):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.config = config
        self.on_input_text = on_input_text
        self.on_output_text = on_output_text
        self.on_audio = on_audio
        self.on_go_away = on_go_away
        self.on_error = on_error

    async def run(self, frames: AsyncIterator[AudioFrame]) -> None:
        async with self.client.aio.live.connect(model=self.model, config=self.config) as session:
            sender = asyncio.create_task(self._send(session, frames))
            receiver = asyncio.create_task(self._receive(session))
            try:
                await asyncio.gather(sender, receiver)
            finally:
                sender.cancel()
                receiver.cancel()

    async def _send(self, session, frames: AsyncIterator[AudioFrame]) -> None:
        async for frame in frames:
            await session.send_realtime_input(
                audio=types.Blob(data=frame.pcm, mime_type="audio/pcm;rate=16000")
            )
        await session.send_realtime_input(audio_stream_end=True)

    async def _receive(self, session) -> None:
        while True:
            async for msg in session.receive():
                await self._dispatch(msg)

    async def _dispatch(self, msg) -> None:
        try:
            content = msg.server_content
            if content is not None:
                interim = content.interim_input_transcription
                if interim is not None and interim.text:
                    await self.on_input_text(interim.text, True)
                final = content.input_transcription
                if final is not None and final.text:
                    await self.on_input_text(final.text, False)
                output = content.output_transcription
                if output is not None and output.text and self.on_output_text:
                    await self.on_output_text(output.text)
                if content.model_turn and self.on_audio:
                    for part in content.model_turn.parts or []:
                        if part.inline_data and part.inline_data.data:
                            await self.on_audio(part.inline_data.data)
            if msg.go_away is not None and self.on_go_away:
                await self.on_go_away(msg.go_away.time_left)
        except Exception as e:
            if self.on_error:
                await self.on_error(e)
            else:
                raise
