import asyncio
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import capacity_error_handler
from backend.config import Settings
from backend.core.capacity import CapacityError, CapacityGuard
from backend.core.manager import SessionManager
from backend.core.session import SessionStatus
from tests.test_session import FakeEngine


class LiveFileEngine(FakeEngine):
    """A Live engine that needs audio: Session.start() rejects it for a room without a file."""

    needs_audio = True


def test_guard_reserve_is_idempotent_and_never_waits():
    guard = CapacityGuard(2)
    guard.reserve("a")
    guard.reserve("a")  # rotation / reconnect of the same room keeps its slot
    guard.reserve("b")
    assert guard.usage() == {"used": 2, "max": 2}
    t = time.monotonic()
    with pytest.raises(CapacityError, match="2/2"):
        guard.reserve("c")
    assert time.monotonic() - t < 0.05  # rejected at once, never queued
    guard.release("a")
    guard.release("a")  # releasing twice is harmless
    guard.reserve("c")
    assert guard.holds("c") and not guard.holds("a")


def test_failed_start_releases_the_slot(tmp_path):
    async def main():
        m = SessionManager(Settings(data_dir=tmp_path, max_concurrent_live=1),
                           engine_factory=lambda: LiveFileEngine(uses_live=True))
        room = m.create("Sin archivo", source="file")  # no file: Session.start() raises
        with pytest.raises(ValueError, match="archivo"):
            m.start(room.id)
        assert m.live_usage() == {"used": 0, "max": 1}
        assert room.status == SessionStatus.CREATED

    asyncio.run(main())


def test_failed_restart_of_a_running_room_keeps_its_slot(tmp_path):
    async def main():
        m = SessionManager(Settings(data_dir=tmp_path, max_concurrent_live=1),
                           engine_factory=lambda: FakeEngine(n=1000, gap=0.05, uses_live=True))
        room = m.create("Sala")
        m.start(room.id)
        with pytest.raises(RuntimeError, match="ya está corriendo"):
            m.start(room.id)
        assert m.capacity.holds(room.id) and room.running
        await m.stop_all()
        await asyncio.sleep(0)  # done callbacks run on the next loop iteration
        assert m.live_usage()["used"] == 0

    asyncio.run(main())


def test_slot_is_released_when_the_engine_fails(tmp_path):
    async def main():
        m = SessionManager(Settings(data_dir=tmp_path, max_concurrent_live=1),
                           engine_factory=lambda: FakeEngine(n=1, fail=True, uses_live=True))
        room = m.create("Sala")
        m.start(room.id)
        await asyncio.gather(room._task)
        await asyncio.sleep(0)
        assert room.status == SessionStatus.ERROR
        assert m.live_usage()["used"] == 0

    asyncio.run(main())


def test_capacity_error_maps_to_409():
    app = FastAPI()
    app.add_exception_handler(CapacityError, capacity_error_handler)

    @app.post("/start")
    def start():
        raise CapacityError("cupo Live lleno (2/2)")

    resp = TestClient(app).post("/start")
    assert resp.status_code == 409
    assert "2/2" in resp.json()["detail"]
