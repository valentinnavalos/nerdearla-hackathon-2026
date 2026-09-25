"""WS ingest / captions / admin / audio — ver T1.11 / T2.6.

Contrato de endpoints (congelado en T0.5):

| Método | Ruta                        | Auth  | Uso                             |
|--------|------------------------------|-------|-----------------------------------|
| WS     | /ws/ingest/{id}?token=       | admin | Audio del mic                    |
| WS     | /ws/captions/{id}?lang=      | --    | Subtítulos                       |
| WS     | /ws/admin?token=             | admin | Snapshot de estado cada 1 s      |

Códigos de cierre propios: 4404 = la sala no existe, 4400 = idioma inválido.
"""

import asyncio

import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.auth import check_ws_token
from backend.core.session import LANGS

router = APIRouter()

INGEST_FRAME_BYTES = 3200  # 100 ms of PCM16 LE 16 kHz mono
INGEST_STATUS_INTERVAL_S = 1.0
ADMIN_SNAPSHOT_INTERVAL_S = 1.0


@router.websocket("/ws/captions/{session_id}")
async def captions(ws: WebSocket, session_id: str, lang: str = "es") -> None:
    """On connect: current status + history of finals for `lang`, then live events as JSON."""
    await ws.accept()  # a custom close code needs an accepted socket
    session = ws.app.state.manager.get(session_id)
    if session is None:
        await ws.close(code=4404, reason="session not found")
        return
    if lang not in LANGS:
        await ws.close(code=4400, reason="lang must be en or es")
        return

    queue = session.subscribe(lang)  # before the history, so no event falls in between
    try:
        await ws.send_json({"type": "session_status", "session_id": session.id, "status": session.status.value})
        for msg in session.history(lang):
            await ws.send_json(msg)
        await _forward(ws, queue)
    except WebSocketDisconnect:
        pass  # left while the history was being sent
    finally:
        session.unsubscribe(lang, queue)


@router.websocket("/ws/ingest/{session_id}")
async def ingest(ws: WebSocket, session_id: str, token: str | None = None) -> None:
    """Mic audio from the stage view (T2.6/T2.7): binary frames of exactly
    INGEST_FRAME_BYTES (100 ms PCM16 16kHz mono); wrong-size frames are dropped."""
    settings = ws.app.state.settings
    if not check_ws_token(settings, token):
        await ws.close(code=4401, reason="unauthorized")
        return
    await ws.accept()
    session = ws.app.state.manager.get(session_id)
    if session is None or session.source != "mic" or session._mic_source is None:
        await ws.close(code=4404, reason="session not found or not a mic room")
        return

    bad_size_frames = 0
    status_task = asyncio.create_task(_ingest_status_loop(ws, session))
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            data = msg.get("bytes")
            if data is None:
                continue
            if len(data) != INGEST_FRAME_BYTES:
                bad_size_frames += 1
                continue
            session.push_audio(data)
    except WebSocketDisconnect:
        pass
    finally:
        status_task.cancel()


@router.websocket("/ws/admin")
async def admin_snapshot(ws: WebSocket, token: str | None = None) -> None:
    """Full state snapshot every 1 s, for the monitoring panel (T3.2)."""
    settings = ws.app.state.settings
    if not check_ws_token(settings, token):
        await ws.close(code=4401, reason="unauthorized")
        return
    await ws.accept()
    manager = ws.app.state.manager
    try:
        while True:
            try:
                await ws.send_json({
                    "type": "admin_snapshot",
                    "sessions": [s.info() for s in manager.list()],
                    "live_usage": manager.live_usage(),
                    "quota": manager.quota_today(),
                })
            except (WebSocketDisconnect, RuntimeError):
                return
            await asyncio.sleep(ADMIN_SNAPSHOT_INTERVAL_S)
    except WebSocketDisconnect:
        pass


async def _ingest_status_loop(ws: WebSocket, session) -> None:
    while True:
        await asyncio.sleep(INGEST_STATUS_INTERVAL_S)
        audio = session._ctx.metrics.snapshot() if session._ctx and session._ctx.metrics else {}
        try:
            await ws.send_json({
                "type": "ingest_status",
                "status": session.status.value,
                "mic_connected": session.mic_connected(),
                "lat_p50_ms": (audio.get("final_latency_ms") or {}).get("p50"),
            })
        except (WebSocketDisconnect, RuntimeError):
            return


async def _forward(ws: WebSocket, queue: asyncio.Queue) -> None:
    """Send queued messages until the client disconnects (detected by a reader task)."""
    async with anyio.create_task_group() as tg:

        async def reader() -> None:
            while (await ws.receive())["type"] != "websocket.disconnect":
                pass
            tg.cancel_scope.cancel()

        async def writer() -> None:
            try:
                while True:
                    await ws.send_json(await queue.get())
            except (WebSocketDisconnect, RuntimeError):  # client gone mid-send
                tg.cancel_scope.cancel()

        tg.start_soon(reader)
        tg.start_soon(writer)
