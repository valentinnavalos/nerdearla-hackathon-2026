"""LiveTranslateEngine + LiveSessionRunner against a fake Gemini Live session (no network)."""

import asyncio
import time
from contextlib import asynccontextmanager

import pytest
from google.genai import types

from backend.core.glossary import Glossary
from backend.engine import live_runner
from backend.engine.base import SessionContext
from backend.engine.live_translate import LiveTranslateEngine
from backend.sources.base import AudioFrame


def _msg(field: str, text: str) -> types.LiveServerMessage:
    return types.LiveServerMessage(
        server_content=types.LiveServerContent(**{field: types.Transcription(text=text)})
    )


class FakeSession:
    def __init__(self, script, close_with=None):
        self.script = script  # [(delay_s, message)]
        self.close_with = close_with
        self.sent = 0
        self.stream_ended = False

    async def send_realtime_input(self, audio=None, audio_stream_end=None):
        if audio is not None:
            self.sent += 1
        if audio_stream_end:
            self.stream_ended = True

    async def receive(self):
        while self.script:
            delay, msg = self.script.pop(0)
            await asyncio.sleep(delay)
            yield msg
        if self.close_with:
            raise self.close_with
        await asyncio.Event().wait()  # socket open, server quiet


class FakeClient:
    def __init__(self, session):
        self.aio = self
        self.live = self
        self.session = session

    @asynccontextmanager
    async def connect(self, model, config):
        yield self.session


def _patch(monkeypatch, session):
    monkeypatch.setattr(live_runner.genai, "Client", lambda api_key: FakeClient(session))


async def _frames(n: int, gap: float = 0.01):
    for _ in range(n):
        await asyncio.sleep(gap)
        yield AudioFrame(pcm=b"\x00" * 3200, t_capture=time.monotonic())


def test_engine_segments_both_tracks_and_returns_after_drain(monkeypatch):
    session = FakeSession([
        (0.05, _msg("input_transcription", "Welcome to")),
        (0.05, _msg("input_transcription", " nerdearla everyone.")),
        (0.05, _msg("output_transcription", "Bienvenidos a")),
        (0.05, _msg("output_transcription", " Nerdearla a todos.")),
        (0.05, _msg("input_transcription", " Today we talk about cubernetes")),
    ])
    _patch(monkeypatch, session)
    events = []

    async def emit(event):
        events.append(event)

    ctx = SessionContext("s1", "en", "es", Glossary.load("config/glossary.default.json"))
    engine = LiveTranslateEngine("key", "model")
    t0 = time.monotonic()
    asyncio.run(engine.run(_frames(10), emit, ctx))
    elapsed = time.monotonic() - t0

    assert session.sent == 10 and session.stream_ended
    assert elapsed < 6  # returns after the 3 s drain, not hanging on the open socket
    finals = [(e.lang, e.kind, e.seg, e.text) for e in events if e.final]
    assert finals == [
        ("en", "orig", 1, "Welcome to Nerdearla everyone."),
        ("es", "trans", 1, "Bienvenidos a Nerdearla a todos."),
        ("en", "orig", 2, "Today we talk about Kubernetes"),  # flushed at the end, glossary applied
    ]
    assert [e.text for e in events if not e.final and e.lang == "en"][0] == "Welcome to"
    stats = engine.runner.stats
    assert stats["frames_sent"] == 10 and stats["msgs"] == 5
    assert stats["connect_ms"] is not None and 0 < stats["first_text_s"] < 1
    assert stats["dispatch_ms_max"] < 50


def test_runner_raises_when_the_server_closes_mid_stream(monkeypatch):
    session = FakeSession([(0.02, _msg("input_transcription", "Hello"))], close_with=RuntimeError("1011 closed"))
    _patch(monkeypatch, session)

    async def emit(event):
        pass

    # a single reconnect attempt with no backoff: fails fast instead of retrying for real time
    engine = LiveTranslateEngine("key", "model", max_reconnect_failures=1, reconnect_backoffs=(0,))
    with pytest.raises(RuntimeError, match="1011"):
        asyncio.run(engine.run(_frames(1000), emit, SessionContext("s1", "en", "es")))


def test_run_forever_rotates_preemptively_and_resumes(monkeypatch):
    """T2.1: rotate_after_s elapses -> reconnect with the resumption handle -> counters update."""
    from backend.engine.live_runner import LiveSessionRunner

    runner = LiveSessionRunner(api_key="key", model="model", config=types.LiveConnectConfig(),
                                on_input_text=lambda *a: asyncio.sleep(0))
    calls: list[str | None] = []

    async def fake_run(frames, resumption_handle=None):
        calls.append(resumption_handle)
        runner.stats = {"resumption_handle": f"handle-{len(calls)}"}
        if len(calls) == 1:
            await asyncio.Event().wait()  # hangs until run_forever cancels it for rotation
        # 2nd call: frames "end" -> return cleanly, run_forever should stop the loop

    monkeypatch.setattr(runner, "run", fake_run)
    states: list[str] = []

    async def on_state(state):
        states.append(state)

    asyncio.run(runner.run_forever(_frames(1), rotate_after_s=0.03, on_state=on_state))

    assert calls == [None, "handle-1"]  # 2nd connect resumed with the 1st connection's handle
    assert runner._rotation_stats["rotations"] == 1
    assert runner._rotation_stats["resumptions"] == 1
    assert "ROTATING" in states


def test_run_forever_raises_after_max_consecutive_failures(monkeypatch):
    from backend.engine.live_runner import LiveSessionRunner

    runner = LiveSessionRunner(api_key="key", model="model", config=types.LiveConnectConfig(),
                                on_input_text=lambda *a: asyncio.sleep(0))

    async def fake_run(frames, resumption_handle=None):
        runner.stats = {"resumption_handle": None}
        raise ConnectionError("network down")

    monkeypatch.setattr(runner, "run", fake_run)
    with pytest.raises(ConnectionError, match="network down"):
        asyncio.run(runner.run_forever(
            _frames(1), rotate_after_s=100, max_consecutive_failures=2, backoffs=(0,)
        ))
    assert runner._rotation_stats["reconnects"] == 1
    assert runner._rotation_stats["fresh_sessions"] == 1
    assert runner._rotation_stats["errors"] == 2
