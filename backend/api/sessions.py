"""REST admin + público (T2.5).

Contrato de endpoints (congelado en T0.5):

| Método   | Ruta                                              | Auth  | Uso                              |
|----------|----------------------------------------------------|-------|-----------------------------------|
| GET      | /healthz                                            | --    | Healthcheck                       |
| GET      | /api/public/sessions                                | --    | Lista pública: id, título, orador, idiomas, estado |
| POST     | /api/sessions                                       | admin | Crear sala                        |
| POST     | /api/sessions/{id}/start                            | admin | Arrancar                          |
| POST     | /api/sessions/{id}/stop                             | admin | Parar                             |
| DELETE   | /api/sessions/{id}                                  | admin | Borrar                            |
| GET      | /api/sessions                                       | admin | Estado completo + métricas        |
| POST     | /api/uploads                                        | admin | Subir mp3                         |
| GET      | /api/sessions/{id}/export.{srt,vtt,txt,md}?lang=    | --    | Exports (T3.3)                    |
| GET      | /api/sessions/{id}/knowledge                        | --    | Knowledge Pack (T3.4)             |
| POST     | /api/sessions/{id}/ask                              | -- (rate limit) | Preguntale a la charla (T3.6) |
"""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel

from backend.api.auth import require_admin

router = APIRouter()

UPLOAD_MAX_BYTES = 100 * 1024 * 1024


class CreateSessionBody(BaseModel):
    title: str
    speaker: str = ""
    source_lang: Literal["en", "es"]
    source: Literal["mic", "file"] = "file"
    file: str | None = None
    loop: bool = False
    glossary_text: str | None = None


@router.get("/healthz")
def healthz(request: Request) -> dict:
    return {"ok": True, "engine": request.app.state.settings.engine}


@router.get("/api/public/sessions")
def public_sessions(request: Request) -> list[dict]:
    return [s.public_info() for s in request.app.state.manager.list()]


@router.post("/api/sessions", dependencies=[Depends(require_admin)])
async def create_session(body: CreateSessionBody, request: Request) -> dict:
    manager = request.app.state.manager
    try:
        session = manager.create(
            title=body.title,
            speaker=body.speaker,
            source_lang=body.source_lang,
            source=body.source,
            file=body.file,
            loop=body.loop,
            glossary_text=body.glossary_text,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return session.info()


@router.post("/api/sessions/{session_id}/start", dependencies=[Depends(require_admin)])
async def start_session(session_id: str, request: Request) -> dict:
    session = request.app.state.manager.start(session_id)
    return session.info()


@router.post("/api/sessions/{session_id}/stop", dependencies=[Depends(require_admin)])
async def stop_session(session_id: str, request: Request) -> dict:
    session = await request.app.state.manager.stop(session_id)
    return session.info()


@router.delete("/api/sessions/{session_id}", dependencies=[Depends(require_admin)])
async def delete_session(session_id: str, request: Request) -> dict:
    await request.app.state.manager.delete(session_id)
    return {"ok": True}


@router.get("/api/sessions", dependencies=[Depends(require_admin)])
def list_sessions(request: Request) -> dict:
    manager = request.app.state.manager
    return {
        "sessions": [s.info() for s in manager.list()],
        "live_usage": manager.live_usage(),
        "quota": manager.quota_today(),
    }


@router.post("/api/uploads", dependencies=[Depends(require_admin)])
async def upload(request: Request, file: UploadFile) -> dict:
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(400, "el archivo debe ser audio/*")
    settings = request.app.state.settings
    dest_dir = Path(settings.data_dir) / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / Path(file.filename or "upload").name
    written = 0
    with dest.open("wb") as f:
        while chunk := await file.read(1024 * 1024):
            written += len(chunk)
            if written > UPLOAD_MAX_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(400, "el archivo supera los 100 MB")
            f.write(chunk)
    return {"file": str(dest)}
