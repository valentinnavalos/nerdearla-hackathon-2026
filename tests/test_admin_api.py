import json

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

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def auth(token: str = TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_admin_routes_require_a_valid_token(client):
    assert client.get("/api/sessions").status_code == 401
    assert client.get("/api/sessions", headers=auth("wrong")).status_code == 401
    assert client.post("/api/sessions", json={"title": "x", "source_lang": "en"}).status_code == 401


def test_create_start_stop_delete_lifecycle(client):
    body = {"title": "Charla de prueba", "source_lang": "en", "source": "file",
            "file": "samples/en_talk_3min.mp3"}
    r = client.post("/api/sessions", json=body, headers=auth())
    assert r.status_code == 200
    session_id = r.json()["id"]
    assert r.json()["status"] == "CREATED"

    r = client.post(f"/api/sessions/{session_id}/start", headers=auth())
    assert r.status_code == 200 and r.json()["status"] == "RUNNING"

    r = client.get("/api/sessions", headers=auth())
    assert r.status_code == 200
    body = r.json()
    assert any(s["id"] == session_id for s in body["sessions"])
    assert "used" in body["live_usage"] and "used" in body["quota"]

    r = client.post(f"/api/sessions/{session_id}/stop", headers=auth())
    assert r.status_code == 200 and r.json()["status"] == "STOPPED"

    r = client.delete(f"/api/sessions/{session_id}", headers=auth())
    assert r.status_code == 200 and r.json() == {"ok": True}

    assert client.get("/api/sessions", headers=auth()).json()["sessions"] == \
        [s for s in client.get("/api/sessions", headers=auth()).json()["sessions"]]  # still 200, room gone
    assert not any(s["id"] == session_id for s in client.get("/api/sessions", headers=auth()).json()["sessions"])


def test_start_missing_session_is_404(client):
    r = client.post("/api/sessions/nope/start", headers=auth())
    assert r.status_code == 404


def test_bad_source_lang_is_400(client):
    r = client.post("/api/sessions", json={"title": "x", "source_lang": "fr"}, headers=auth())
    assert r.status_code == 422  # pydantic Literal rejects it before it reaches the manager


def test_capacity_exceeded_is_409(client, monkeypatch):
    from backend.config import get_settings as gs
    gs().max_concurrent_live = 0  # no live slots at all
    r = client.post("/api/sessions", json={"title": "x", "source_lang": "en", "source": "file",
                                            "file": "samples/en_talk_3min.mp3"}, headers=auth())
    session_id = r.json()["id"]
    # replay engine never uses Live, so force it through a fake: monkeypatch factory result
    import backend.core.manager as manager_mod

    class FakeLiveEngine:
        uses_live = True
        needs_audio = False

        async def run(self, frames, emit, ctx):
            import asyncio
            await asyncio.sleep(10)

    app = client.app
    app.state.manager._engine_factory = lambda: FakeLiveEngine()
    r = client.post(f"/api/sessions/{session_id}/start", headers=auth())
    assert r.status_code == 409


def test_upload_rejects_non_audio(client, tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("hi")
    with f.open("rb") as fh:
        r = client.post("/api/uploads", headers=auth(), files={"file": ("notes.txt", fh, "text/plain")})
    assert r.status_code == 400
