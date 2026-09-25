import asyncio
import json
import time

import pytest

from backend.config import Settings
from backend.core.events import CaptionEvent
from backend.core import persistence
from backend.core.manager import CapacityError, SessionManager
from backend.core.session import HISTORY_SIZE, SUBSCRIBER_QUEUE_SIZE, SessionStatus
from backend.engine.base import Engine


class FakeEngine(Engine):
    """Emits `n` finals per language, one every `gap` seconds, then (optionally) fails."""

    needs_audio = False

    def __init__(self, n: int = 3, gap: float = 0.0, fail: bool = False, uses_live: bool = False):
        self.n, self.gap, self.fail, self.uses_live = n, gap, fail, uses_live

    async def run(self, frames, emit, ctx):
        for i in range(1, self.n + 1):
            for lang, kind in ((ctx.source_lang, "orig"), (ctx.target_lang, "trans")):
                await emit(CaptionEvent(
                    session_id=ctx.session_id, lang=lang, kind=kind, seg=i,
                    final=True, text=f"{lang} {i}", t0=i, t1=i,
                ))
            await asyncio.sleep(self.gap)
        if self.fail:
            raise RuntimeError("boom")


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, max_concurrent_live=2)


def _manager(engine: Engine, settings: Settings) -> SessionManager:
    return SessionManager(settings, engine_factory=lambda: engine)


def _drain(queue: asyncio.Queue) -> list[dict]:
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


def test_subscribers_only_get_their_language(settings):
    async def main():
        m = _manager(FakeEngine(n=3, gap=0.01), settings)
        s = m.create("Charla de prueba", source_lang="en")
        q_en, q_es = m.subscribe(s.id, "en"), m.subscribe(s.id, "es")
        m.start(s.id)
        await asyncio.sleep(0.2)
        return s, _drain(q_en), _drain(q_es)

    s, en, es = asyncio.run(main())
    captions_en = [m for m in en if m["type"] == "caption"]
    captions_es = [m for m in es if m["type"] == "caption"]
    assert [m["text"] for m in captions_en] == ["en 1", "en 2", "en 3"]
    assert [m["text"] for m in captions_es] == ["es 1", "es 2", "es 3"]
    assert s.status == SessionStatus.STOPPED
    assert en[-1] == {"type": "session_status", "session_id": s.id, "status": "STOPPED"}


def test_slow_subscriber_never_blocks_and_history_is_capped(settings):
    async def main():
        m = _manager(FakeEngine(n=SUBSCRIBER_QUEUE_SIZE + 20), settings)
        s = m.create("Sala", source_lang="es")
        slow = m.subscribe(s.id, "en")  # never read
        m.start(s.id)
        await asyncio.wait_for(s._task, timeout=2)
        return s, slow

    s, slow = asyncio.run(main())
    assert slow.qsize() == SUBSCRIBER_QUEUE_SIZE
    assert len(s.history("en")) == HISTORY_SIZE
    assert s.history("en")[-1]["text"] == f"en {SUBSCRIBER_QUEUE_SIZE + 20}"


def test_engine_exception_marks_error_without_raising(settings):
    async def main():
        m = _manager(FakeEngine(n=1, fail=True), settings)
        s = m.create("Rota", source_lang="en")
        m.start(s.id)
        await asyncio.wait_for(s._task, timeout=2)
        return s

    s = asyncio.run(main())
    assert s.status == SessionStatus.ERROR
    assert s.last_error == "RuntimeError: boom"


def test_one_broken_room_never_affects_another(settings):
    """T2.2: a crash in one room's engine.run() must not touch a sibling room."""
    engines = {}

    def factory():
        # first room built fails immediately, the rest keep emitting
        engine = FakeEngine(n=1, fail=True) if not engines else FakeEngine(n=1000, gap=0.02)
        engines[len(engines)] = engine
        return engine

    async def main():
        m = SessionManager(settings, engine_factory=factory)
        broken = m.create("Rota", source_lang="en")
        healthy = m.create("Sana", source_lang="en")
        m.start(broken.id)
        m.start(healthy.id)

        await asyncio.wait_for(broken._task, timeout=2)
        await asyncio.sleep(0.1)
        assert healthy.status == SessionStatus.RUNNING and healthy.running
        await m.stop(healthy.id)
        return broken, healthy

    broken, healthy = asyncio.run(main())
    assert broken.status == SessionStatus.ERROR
    assert healthy.status == SessionStatus.STOPPED


def test_stop_cancels_a_running_session(settings):
    async def main():
        m = _manager(FakeEngine(n=1000, gap=0.05), settings)
        s = m.create("Larga", source_lang="en")
        m.start(s.id)
        await asyncio.sleep(0.1)
        await m.stop(s.id)
        return s

    s = asyncio.run(main())
    assert s.status == SessionStatus.STOPPED
    assert not s.running


def test_ids_are_unique_slugs_and_glossary_is_merged(settings):
    m = SessionManager(settings, engine_factory=FakeEngine)
    a = m.create("Diseño de APIs", source_lang="es", glossary_text="gRPC\ngerpc => gRPC")
    b = m.create("Diseño de APIs", source_lang="es")
    assert (a.id, b.id) == ("diseno-de-apis", "diseno-de-apis-2")
    assert a.target_lang == "en"
    assert a.glossary.apply("usamos gerpc en kubernetes") == "usamos gRPC en Kubernetes"


def test_capacity_guard_rejects_a_third_live_room_at_start(settings):
    async def main():
        m = SessionManager(settings, engine_factory=lambda: FakeEngine(n=1000, gap=0.05, uses_live=True))
        rooms = [m.create(f"Sala {i}") for i in range(3)]
        m.start(rooms[0].id)
        m.start(rooms[1].id)
        with pytest.raises(CapacityError, match="2/2"):
            m.start(rooms[2].id)
        assert rooms[2].status == SessionStatus.CREATED and not rooms[2].running
        assert m.live_usage() == {"used": 2, "max": 2}
        await m.stop(rooms[0].id)  # frees its slot
        m.start(rooms[2].id)
        assert m.live_usage() == {"used": 2, "max": 2}
        replay = SessionManager(settings, engine_factory=lambda: FakeEngine(n=1000, gap=0.05))
        others = [replay.create(f"Replay {i}") for i in range(3)]
        for room in others:
            replay.start(room.id)  # engines without Live never count
        assert replay.live_usage()["used"] == 0
        await m.stop_all()
        await replay.stop_all()
        assert m.live_usage()["used"] == 0

    asyncio.run(main())


def test_reload_brings_back_stopped_rooms_from_disk(settings):
    """T2.3: meta.json + captions.jsonl survive a process restart."""
    async def main():
        m = _manager(FakeEngine(n=3, gap=0.0), settings)
        s = m.create("Charla Grabada", source_lang="en", speaker="Ana")
        m.start(s.id)
        await asyncio.wait_for(s._task, timeout=2)
        return s

    original = asyncio.run(main())
    assert original.status == SessionStatus.STOPPED

    reloaded_manager = SessionManager(settings, engine_factory=lambda: FakeEngine())
    reloaded_manager.reload()
    reloaded = reloaded_manager.get(original.id)
    assert reloaded is not None
    assert reloaded.status == SessionStatus.STOPPED
    assert reloaded.speaker == "Ana"
    assert reloaded.public_info()["title"] == "Charla Grabada"
    assert len(reloaded.history("en")) == 3
    assert reloaded.history("en")[-1]["text"] == "en 3"

    # a RUNNING room is never resumed after a restart
    running_meta = original.meta_path.read_text()
    import json as _json
    meta = _json.loads(running_meta)
    meta["status"] = "RUNNING"
    original.meta_path.write_text(_json.dumps(meta))
    yet_another_manager = SessionManager(settings, engine_factory=lambda: FakeEngine())
    yet_another_manager.reload()
    assert yet_another_manager.get(original.id) is None


def test_slow_disk_never_delays_emit_nor_other_rooms(settings, monkeypatch):
    original_append = persistence.CaptionWriter._append

    def slow_append(self, lines):
        time.sleep(0.3)  # runs in a thread: must not block the event loop
        original_append(self, lines)

    monkeypatch.setattr(persistence.CaptionWriter, "_append", slow_append)

    async def main():
        m = _manager(FakeEngine(n=20, gap=0.05), settings)
        a, b = m.create("Sala A", source_lang="en"), m.create("Sala B", source_lang="es")
        q_b = m.subscribe(b.id, "es")
        m.start(a.id)
        m.start(b.id)
        arrivals = []
        while len(arrivals) < 20:
            msg = await asyncio.wait_for(q_b.get(), timeout=1)
            if msg["type"] == "caption":
                arrivals.append(time.monotonic())
        await asyncio.gather(a._task, b._task)
        await asyncio.gather(a.stop(), b.stop())
        return a, arrivals

    a, arrivals = asyncio.run(main())
    gaps = [y - x for x, y in zip(arrivals, arrivals[1:])]
    assert max(gaps) < 0.2  # room B keeps its 50 ms pace while every write takes 300 ms
    lines = [json.loads(line) for line in a.captions_path.read_text().splitlines()]
    assert [line["text"] for line in lines if line["lang"] == "en"] == [f"en {i}" for i in range(1, 21)]
    assert all(line["final"] for line in lines) and len(lines) == 40
    assert a.info()["metrics"]["captions_written"] == 40
