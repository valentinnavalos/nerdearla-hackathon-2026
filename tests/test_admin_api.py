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

    r = client.get("/api/sessions", headers=auth())
    assert r.status_code == 200  # still 200, room gone
    assert not any(s["id"] == session_id for s in r.json()["sessions"])


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


def _room_with_captions(client) -> str:
    """A CREATED room with a captions.jsonl on disk: enough for /knowledge and /ask."""
    r = client.post("/api/sessions", json={"title": "Charla KP", "source_lang": "en"}, headers=auth())
    session_id = r.json()["id"]
    session = client.app.state.manager.get(session_id)
    session.captions_path.parent.mkdir(parents=True, exist_ok=True)
    session.captions_path.write_text(json.dumps(
        {"lang": "en", "kind": "orig", "text": "Kubernetes schedules pods", "t0": 61, "final": True}) + "\n")
    return session_id


def test_knowledge_endpoint_and_md_export_with_the_pack(client):
    session_id = _room_with_captions(client)
    r = client.get(f"/api/sessions/{session_id}/knowledge")
    assert r.status_code == 200
    assert r.json() == {"kp_status": None, "knowledge": None, "notebooklm_url": None}

    session = client.app.state.manager.get(session_id)
    session.knowledge_path.write_text(json.dumps({"summary_es": "Un resumen.", "key_points": []}))
    session.kp_status = "ready"
    r = client.get(f"/api/sessions/{session_id}/knowledge")
    assert r.json()["kp_status"] == "ready" and r.json()["knowledge"]["summary_es"] == "Un resumen."
    assert "## Resumen" in client.get(f"/api/sessions/{session_id}/export.md").text

    session.knowledge_path.unlink()  # lost disk: "ready" without a file reads as an error
    assert client.get(f"/api/sessions/{session_id}/knowledge").json()["kp_status"] == "error"
    assert client.get("/api/sessions/nope/knowledge").status_code == 404


def test_regenerate_requires_admin_and_runs_the_pipeline(client):
    session_id = _room_with_captions(client)
    ran: list[str] = []

    async def fake_post(session):
        ran.append(session.id)

    client.app.state.manager._post_processor = fake_post
    assert client.post(f"/api/sessions/{session_id}/knowledge/regenerate").status_code == 401
    r = client.post(f"/api/sessions/{session_id}/knowledge/regenerate", headers=auth())
    assert r.status_code == 200
    assert ran == [session_id]


def test_ask_validates_caches_and_rate_limits(client, monkeypatch):
    from backend.post import knowledge

    session_id = _room_with_captions(client)
    url = f"/api/sessions/{session_id}/ask"
    assert client.post(url, json={"q": "¿qué es?"}).status_code == 503  # no GEMINI_API_KEY

    client.app.state.settings.gemini_api_key = "k"
    asked: list[str] = []

    async def fake_ask(c, model, meta, transcript, question):
        asked.append(question)
        assert "[01:01] Kubernetes schedules pods" in transcript
        return f"Respuesta [01:01] a {question}"

    monkeypatch.setattr(knowledge, "ask", fake_ask)
    assert client.post(url, json={"q": ""}).status_code == 422
    assert client.post(url, json={"q": "x" * 301}).status_code == 422

    r = client.post(url, json={"q": "¿Qué hace Kubernetes?"})
    assert r.status_code == 200 and "[01:01]" in r.json()["answer"] and r.json()["cached"] is False
    r = client.post(url, json={"q": "que hace kubernetes"})  # same normalized question
    assert r.json()["cached"] is True and len(asked) == 1

    for i in range(4):  # 1 used above + 4 = the limit of 5
        assert client.post(url, json={"q": f"pregunta {i}"}).status_code == 200
    r = client.post(url, json={"q": "la sexta"})
    assert r.status_code == 429
    assert client.post(url, json={"q": "¿Qué hace Kubernetes?"}).status_code == 200  # cache hits are free


def test_ask_maps_gemini_429_to_a_friendly_429(client, monkeypatch):
    from google.genai import errors
    from backend.post import knowledge

    session_id = _room_with_captions(client)
    client.app.state.settings.gemini_api_key = "k"

    async def busy(*args):
        raise errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})

    monkeypatch.setattr(knowledge, "ask", busy)
    r = client.post(f"/api/sessions/{session_id}/ask", json={"q": "hola"})
    assert r.status_code == 429 and "Mucha demanda" in r.json()["detail"]
