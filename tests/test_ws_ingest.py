import pytest
from fastapi.testclient import TestClient

from backend.config import get_settings

TOKEN = "s3cr3t"
FRAME_BYTES = 3200


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


def _mic_room(client):
    from backend.core.events import CaptionEvent
    from backend.engine.base import Engine

    class EchoMicEngine(Engine):
        """Emits one final per received frame's byte length, so the test can see push_audio() worked."""

        needs_audio = True

        async def run(self, frames, emit, ctx):
            i = 0
            async for frame in frames:
                i += 1
                await emit(CaptionEvent(
                    session_id=ctx.session_id, lang=ctx.source_lang, kind="orig",
                    seg=i, final=True, text=f"frame {i} bytes={len(frame.pcm)}", t0=i, t1=i,
                ))

    manager = client.app.state.manager
    manager._engine_factory = lambda: EchoMicEngine()
    r = client.post("/api/sessions", json={"title": "Mic Room", "source_lang": "en", "source": "mic"},
                     headers={"Authorization": f"Bearer {TOKEN}"})
    session_id = r.json()["id"]
    client.post(f"/api/sessions/{session_id}/start", headers={"Authorization": f"Bearer {TOKEN}"})
    return manager.get(session_id)


def test_ingest_requires_a_valid_token(client):
    from starlette.websockets import WebSocketDisconnect

    session = _mic_room(client)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/ingest/{session.id}") as ws:
            ws.receive_bytes()
    assert exc.value.code == 4401


def test_ingest_feeds_captions_and_drops_wrong_size_frames(client):
    session = _mic_room(client)
    caps = client.websocket_connect(f"/ws/captions/{session.id}?lang=en")
    with caps as cap_ws:
        cap_ws.receive_json()  # status
        with client.websocket_connect(f"/ws/ingest/{session.id}?token={TOKEN}") as ws:
            ws.send_bytes(b"\x00" * FRAME_BYTES)
            ws.send_bytes(b"\x00" * 10)  # wrong size, dropped
            ws.send_bytes(b"\x00" * FRAME_BYTES)
            msg1 = cap_ws.receive_json()
            msg2 = cap_ws.receive_json()
    assert msg1["text"] == f"frame 1 bytes={FRAME_BYTES}"
    assert msg2["text"] == f"frame 2 bytes={FRAME_BYTES}"


def test_ingest_unknown_or_non_mic_session_closes_4404(client):
    from starlette.websockets import WebSocketDisconnect

    file_session = client.app.state.manager.create("File Room", source_lang="en", source="file",
                                                     file="samples/en_talk_3min.mp3")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/ingest/{file_session.id}?token={TOKEN}") as ws:
            ws.receive_bytes()
    assert exc.value.code == 4404
