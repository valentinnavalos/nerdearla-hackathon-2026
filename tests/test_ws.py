import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.config import get_settings
from backend.engine.base import SessionContext
from backend.engine.replay import ReplayEngine

EVENTS = [
    {"session_id": "x", "lang": "en", "kind": "orig", "seg": 1, "final": False, "text": "Hello", "t0": 10.0, "t1": 10.0},
    {"session_id": "x", "lang": "es", "kind": "trans", "seg": 1, "final": False, "text": "Hola", "t0": 10.0, "t1": 10.5},
    {"session_id": "x", "lang": "en", "kind": "orig", "seg": 1, "final": True, "text": "Hello world.", "t0": 10.0, "t1": 10.6},
    {"session_id": "x", "lang": "es", "kind": "trans", "seg": 1, "final": True, "text": "Hola mundo.", "t0": 10.0, "t1": 10.7},
]


@pytest.fixture
def replay_file(tmp_path):
    path = tmp_path / "replay.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in EVENTS) + "\n")
    return path


@pytest.fixture
def client(monkeypatch, replay_file, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENGINE", "replay")
    monkeypatch.setenv("REPLAY_FILE", str(replay_file))
    get_settings.cache_clear()
    from backend.app import app

    async def seed():
        session = app.state.manager.create("Demo", speaker="Replay de ejemplo", source_lang="en")
        app.state.manager.start(session.id)

    with TestClient(app) as c:
        c.portal.call(seed)
        yield c
    get_settings.cache_clear()


def test_replay_keeps_pace_and_shifts_segments_per_lap(replay_file):
    async def main():
        got = []

        async def emit(event):
            got.append((round(time.monotonic() - t0, 1), event))

        t0 = time.monotonic()
        engine = ReplayEngine(str(replay_file), loop=True)
        task = asyncio.create_task(engine.run(None, emit, SessionContext("demo", "en", "es")))
        await asyncio.sleep(3.0)  # one lap = 0.7 s of events + 2 s pause
        task.cancel()
        return got

    got = asyncio.run(main())
    assert [t for t, _ in got[:4]] == [0.0, 0.5, 0.6, 0.7]
    assert all(e.session_id == "demo" for _, e in got)
    lap2 = [e for _, e in got[4:]]
    assert lap2 and lap2[0].seg == 3 and lap2[0].t0 == 12.7


def test_healthz_and_public_sessions(client):
    assert client.get("/healthz").json() == {"ok": True, "engine": "replay"}
    sessions = client.get("/api/public/sessions").json()
    assert [s["id"] for s in sessions] == ["demo"]
    assert sessions[0]["status"] == "RUNNING"


def test_captions_ws_sends_status_then_only_its_language(client):
    with client.websocket_connect("/ws/captions/demo?lang=es") as ws:
        first = ws.receive_json()
        assert first["type"] == "session_status"
        received = [ws.receive_json() for _ in range(2)]
    assert [(m["lang"], m["text"]) for m in received] == [("es", "Hola"), ("es", "Hola mundo.")]


def test_captions_ws_sends_history_to_late_joiners(client):
    time.sleep(1.0)  # the first lap is over: both finals are in the history
    with client.websocket_connect("/ws/captions/demo?lang=en") as ws:
        ws.receive_json()  # status
        assert ws.receive_json()["text"] == "Hello world."


def test_captions_ws_unknown_session_closes_4404(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/captions/nope?lang=es") as ws:
            ws.receive_json()
    assert exc.value.code == 4404


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()
