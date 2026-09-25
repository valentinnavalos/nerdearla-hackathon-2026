import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings

TOKEN = "s3cr3t"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ENGINE", "replay")
    monkeypatch.setenv("ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("REPLAY_FILE", "samples/replay_demo.jsonl")
    get_settings.cache_clear()
    from backend.app import app

    async def seed():
        session = app.state.manager.create("Demo", speaker="Replay de ejemplo", source_lang="en")
        app.state.manager.start(session.id)

    with TestClient(app) as c:
        c.portal.call(seed)
        yield c
    get_settings.cache_clear()


def test_admin_ws_rejects_bad_token(client):
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/admin?token=wrong"):
            pass


def test_admin_ws_sends_periodic_snapshot(client):
    with client.websocket_connect(f"/ws/admin?token={TOKEN}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "admin_snapshot"
        assert "sessions" in msg and "live_usage" in msg and "quota" in msg
        assert any(s["id"] == "demo" for s in msg["sessions"])
        demo = next(s for s in msg["sessions"] if s["id"] == "demo")
        assert "uptime_s" in demo and "mic_connected" in demo
