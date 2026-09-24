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

from backend.core.session import LANGS

router = APIRouter()


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
