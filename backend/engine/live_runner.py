import asyncio
import logging
import random
import time
from typing import Any, AsyncIterable, Awaitable, Callable

from google import genai
from google.genai import types

from backend.sources.base import AudioFrame

OnInputText = Callable[[str, bool], Awaitable[None]]  # (text, is_interim)
OnOutputText = Callable[[str], Awaitable[None]]
OnAudio = Callable[[bytes], Awaitable[None]]  # pcm24k, unused for now
OnGoAway = Callable[[Any], Awaitable[None]]
OnError = Callable[[Exception], Awaitable[None]]
OnRaw = Callable[[types.LiveServerMessage], Awaitable[None]]  # every message, for the spike

_log = logging.getLogger("backend.engine")


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
        on_raw: OnRaw | None = None,
        drain_idle_s: float = 3.0,
        drain_max_s: float = 30.0,  # translated audio keeps streaming well after the input ends
        log: logging.Logger | logging.LoggerAdapter | None = None,
    ):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.config = config
        self.on_input_text = on_input_text
        self.on_output_text = on_output_text
        self.on_audio = on_audio
        self.on_go_away = on_go_away
        self.on_error = on_error
        self.on_raw = on_raw
        self.drain_idle_s = drain_idle_s
        self.drain_max_s = drain_max_s
        self.log = log or _log
        self._last_msg_at = 0.0
        self._connected_at = 0.0
        # rotation/resilience counters (T2.1): survive across run() calls, unlike the
        # per-connection fields below, so run_forever() can report cumulative totals.
        self._rotation_stats: dict[str, Any] = {
            "state": "RUNNING",
            "rotations": 0,
            "resumptions": 0,
            "fresh_sessions": 0,
            "reconnects": 0,
            "errors": 0,
            "last_error": None,
        }
        self.stats: dict[str, Any] = dict(self._rotation_stats)

    async def run(self, frames: AsyncIterable[AudioFrame], resumption_handle: str | None = None) -> None:
        """Connect once and run until the source ends and the server goes quiet;
        raise if the session dies. `resumption_handle`, if given, resumes a prior
        session instead of starting a fresh one (T2.1)."""
        self.stats = {
            "connect_ms": None,
            "frames_sent": 0,
            "msgs": 0,
            "first_msg_s": None,  # seconds after connecting
            "first_text_s": None,
            "last_msg_at": None,  # time.monotonic()
            "go_away_time_left": None,
            "generation_complete": 0,
            "resumption_handle": resumption_handle,  # latest one, for resuming the session (T2.1)
            "last_consumed_index": None,
            "dispatch_ms_max": 0.0,  # callbacks must never block the receive loop
        }
        self.stats.update(self._rotation_stats)
        self.config.session_resumption = types.SessionResumptionConfig(
            transparent=True, handle=resumption_handle
        )
        t_connect = time.monotonic()
        try:
            async with self.client.aio.live.connect(model=self.model, config=self.config) as session:
                self._connected_at = self._last_msg_at = time.monotonic()
                self.stats["connect_ms"] = int((self._connected_at - t_connect) * 1000)
                self.log.info("live connected to %s in %d ms", self.model, self.stats["connect_ms"])
                sender = asyncio.create_task(self._send(session, frames))
                receiver = asyncio.create_task(self._receive(session))
                try:
                    done, _ = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
                    if sender in done:
                        sender.result()
                        await self._drain(receiver)
                    else:
                        receiver.result()
                        raise ConnectionError("Live session closed by the server")
                finally:
                    for task in (sender, receiver):
                        task.cancel()
                    await asyncio.gather(sender, receiver, return_exceptions=True)
        except asyncio.CancelledError:
            self.log.info("live cancelled (%s)", self._summary())
            raise
        except Exception as e:
            self.log.warning("live closed with %s: %s (%s)", type(e).__name__, e, self._summary())
            raise
        self.log.info("live closed (%s)", self._summary())

    def _summary(self) -> str:
        st = self.stats
        first = f"{st['first_text_s']:.1f}s" if st["first_text_s"] is not None else "never"
        return (f"frames_sent={st['frames_sent']} msgs={st['msgs']} first_text={first} "
                f"dispatch_ms_max={st['dispatch_ms_max']:.1f}")

    async def _send(self, session, frames: AsyncIterable[AudioFrame]) -> None:
        async for frame in frames:
            await session.send_realtime_input(
                audio=types.Blob(data=frame.pcm, mime_type="audio/pcm;rate=16000")
            )
            self.stats["frames_sent"] += 1
        await session.send_realtime_input(audio_stream_end=True)

    async def _drain(self, receiver: asyncio.Task) -> None:
        """After audio_stream_end, keep receiving until no message arrives for drain_idle_s."""
        deadline = time.monotonic() + self.drain_max_s
        while not receiver.done() and time.monotonic() < deadline:
            if time.monotonic() - self._last_msg_at >= self.drain_idle_s:
                return
            await asyncio.sleep(0.2)
        if receiver.done():
            receiver.result()

    async def _receive(self, session) -> None:
        # receive() ends after each completed turn, so it has to be re-entered
        while True:
            got_any = False
            async for msg in session.receive():
                got_any = True
                self._last_msg_at = time.monotonic()
                self._track(msg)
                t = time.perf_counter()
                await self._dispatch(msg)
                dispatch_ms = (time.perf_counter() - t) * 1000
                self.stats["dispatch_ms_max"] = max(self.stats["dispatch_ms_max"], dispatch_ms)
            if not got_any:
                return

    def _track(self, msg) -> None:
        """Lifecycle stats + logs for one server message (T2.4 builds its metrics on these)."""
        st = self.stats
        since = self._last_msg_at - self._connected_at
        st["msgs"] += 1
        st["last_msg_at"] = self._last_msg_at
        if st["first_msg_s"] is None:
            st["first_msg_s"] = since
        content = msg.server_content
        if content is not None:
            has_text = any(
                tr is not None and tr.text
                for tr in (content.input_transcription, content.interim_input_transcription,
                           content.output_transcription)
            )
            if has_text and st["first_text_s"] is None:
                st["first_text_s"] = since
                self.log.info("live first transcription after %.1f s", since)
            if content.generation_complete:
                st["generation_complete"] += 1
        update = msg.session_resumption_update
        if update is not None:
            if update.new_handle:
                st["resumption_handle"] = update.new_handle
            st["last_consumed_index"] = update.last_consumed_client_message_index
        if msg.go_away is not None:
            st["go_away_time_left"] = str(msg.go_away.time_left)
            self.log.warning("live GoAway after %.0f s, time_left=%s", since, msg.go_away.time_left)

    async def _dispatch(self, msg) -> None:
        try:
            if self.on_raw:
                await self.on_raw(msg)
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

    async def run_forever(
        self,
        frames: AsyncIterable[AudioFrame],
        rotate_after_s: float,
        max_consecutive_failures: int = 10,
        backoffs: tuple[float, ...] = (1, 2, 4, 8, 16),
        backoff_cap: float = 30.0,
        on_state: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        """Keep the room subtitled across the ~10 min connection lifetime of a single
        Live session (T2.1): rotate preventively every `rotate_after_s` (or sooner on
        GoAway) using session resumption, and reconnect with backoff on failure.
        Returns only when `frames` itself is exhausted (the room's source ended);
        raises after `max_consecutive_failures` reconnect attempts in a row fail."""
        handle: str | None = None
        consecutive_failures = 0
        go_away_event = asyncio.Event()
        user_on_go_away = self.on_go_away

        async def _on_go_away(time_left) -> None:
            if user_on_go_away:
                await user_on_go_away(time_left)
            go_away_event.set()

        self.on_go_away = _on_go_away

        async def set_state(state: str) -> None:
            self._rotation_stats["state"] = state
            self.stats["state"] = state
            if on_state:
                await on_state(state)

        try:
            while True:
                go_away_event.clear()
                rotate_task = asyncio.create_task(asyncio.sleep(rotate_after_s))
                go_away_task = asyncio.create_task(go_away_event.wait())
                run_task = asyncio.create_task(self.run(frames, resumption_handle=handle))
                done, _ = await asyncio.wait(
                    {rotate_task, go_away_task, run_task}, return_when=asyncio.FIRST_COMPLETED
                )

                if run_task in done:
                    rotate_task.cancel()
                    go_away_task.cancel()
                    exc = run_task.exception()
                    if exc is None:
                        # frames source itself ended (file done, not looping) - stop cleanly.
                        await set_state("RUNNING")
                        return
                    consecutive_failures += 1
                    self._rotation_stats["errors"] += 1
                    self._rotation_stats["last_error"] = f"{type(exc).__name__}: {exc}"
                    if consecutive_failures >= max_consecutive_failures:
                        await set_state("ERROR")
                        raise exc
                    await set_state("RECONNECTING")
                    handle = self.stats.get("resumption_handle")
                    if handle:
                        self._rotation_stats["resumptions"] += 1
                    else:
                        self._rotation_stats["fresh_sessions"] += 1
                    self._rotation_stats["reconnects"] += 1
                    delay = backoffs[min(consecutive_failures - 1, len(backoffs) - 1)]
                    delay = min(delay, backoff_cap) + random.uniform(0, delay * 0.1)
                    self.log.warning("live reconnecting in %.1fs (attempt %d): %s",
                                      delay, consecutive_failures, self._rotation_stats["last_error"])
                    await asyncio.sleep(delay)
                    continue

                # rotate_task or go_away_task finished first: proactive rotation.
                for t in (rotate_task, go_away_task):
                    if t not in done:
                        t.cancel()
                await set_state("ROTATING")
                run_task.cancel()
                try:
                    await run_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.log.warning("live: error while cancelling for rotation: %s", e)
                consecutive_failures = 0
                handle = self.stats.get("resumption_handle")
                self._rotation_stats["rotations"] += 1
                if handle:
                    self._rotation_stats["resumptions"] += 1
                else:
                    self._rotation_stats["fresh_sessions"] += 1
                self.log.info("live rotating (resumed=%s, rotations=%d)",
                               bool(handle), self._rotation_stats["rotations"])
        finally:
            self.on_go_away = user_on_go_away
