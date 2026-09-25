"""REST admin + público (T2.5).

Contrato de endpoints (congelado en T0.5):

| Método   | Ruta                                              | Auth  | Uso                              |
|----------|----------------------------------------------------|-------|-----------------------------------|
| GET      | /healthz                                            | --    | Healthcheck                       |
| GET      | /api/network-info                                   | --    | IP de LAN, para el QR del escenario |
| GET      | /api/public/sessions                                | --    | Lista pública: id, título, orador, idiomas, estado |
| POST     | /api/sessions                                       | admin | Crear sala                        |
| POST     | /api/sessions/{id}/start                            | admin | Arrancar                          |
| POST     | /api/sessions/{id}/stop                             | admin | Parar                             |
| DELETE   | /api/sessions/{id}                                  | admin | Borrar                            |
| GET      | /api/sessions                                       | admin | Estado completo + métricas        |
| POST     | /api/uploads                                        | admin | Subir mp3                         |
| GET      | /api/sessions/{id}/export.{srt,vtt,txt,md}?lang=    | --    | Exports (T3.3)                    |
| GET      | /api/sessions/{id}/knowledge                        | --    | Knowledge Pack (T3.4)             |
| POST     | /api/sessions/{id}/knowledge/regenerate             | admin | Volver a generar el Knowledge Pack |
| POST     | /api/sessions/{id}/ask                              | -- (rate limit) | Preguntale a la charla (T3.6) |
"""

import socket
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from backend.api.auth import require_admin
from backend.api.ratelimit import client_ip, normalize_question
from backend.core.persistence import load_captions
from backend.post import exports, knowledge

router = APIRouter()


def get_lan_ip() -> str | None:
    """Best-effort LAN-facing IP (no packets actually sent, just picks the
    outbound interface), so the stage view's QR works for phones on the same
    Wi-Fi even when the operator opened it via localhost."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None

UPLOAD_MAX_BYTES = 100 * 1024 * 1024

EXPORT_MEDIA_TYPES = {
    "srt": "application/x-subrip",
    "vtt": "text/vtt",
    "txt": "text/plain",
    "md": "text/markdown",
}


class CreateSessionBody(BaseModel):
    title: str
    speaker: str = ""
    source_lang: Literal["en", "es"]
    source: Literal["mic", "file"] = "file"
    file: str | None = None
    loop: bool = False
    glossary_text: str | None = None


class AskBody(BaseModel):
    q: str = Field(min_length=1, max_length=knowledge.ASK_MAX_CHARS)


@router.get("/healthz")
def healthz(request: Request) -> dict:
    return {"ok": True, "engine": request.app.state.settings.engine}


@router.get("/api/network-info")
def network_info() -> dict:
    return {"lan_ip": get_lan_ip()}


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


@router.get("/api/sessions/{session_id}/export.{fmt}")
def export_session(session_id: str, fmt: str, request: Request, lang: str = "es") -> PlainTextResponse:
    if fmt not in EXPORT_MEDIA_TYPES:
        raise HTTPException(400, f"formato inválido: {fmt}")
    session = request.app.state.manager.get(session_id)
    if session is None:
        raise HTTPException(404, "sala no encontrada")
    events = load_captions(session.captions_path) if session.captions_path else []
    if fmt == "md":
        # with the Knowledge Pack on top, the same MD is the "Copiar para NotebookLM" source (capa 3)
        kp = knowledge.load(session.knowledge_path) if session.kp_status == "ready" else None
        body = exports.to_md(session.meta(), exports.group_by_lang(events), kp)
    else:
        if lang not in ("en", "es"):
            raise HTTPException(400, "lang debe ser 'en' o 'es'")
        lang_events = [e for e in events if e.get("lang") == lang]
        if fmt == "txt":
            body = exports.to_txt(lang_events)
        else:
            offset_ms = exports.median_latency_ms(lang_events)
            cues = exports.build_cues(lang_events, offset_ms=offset_ms)
            body = exports.to_srt(cues) if fmt == "srt" else exports.to_vtt(cues)
    return PlainTextResponse(body, media_type=EXPORT_MEDIA_TYPES[fmt])


@router.get("/api/sessions/{session_id}/knowledge")
def get_knowledge(session_id: str, request: Request) -> dict:
    session = request.app.state.manager.get(session_id)
    if session is None:
        raise HTTPException(404, "sala no encontrada")
    kp = knowledge.load(session.knowledge_path) if session.kp_status == "ready" else None
    kp_status = session.kp_status
    if kp_status == "ready" and kp is None:  # knowledge.json is gone (e.g. Render without a disk)
        kp_status = "error"
    return {
        "kp_status": kp_status,
        "knowledge": kp,
        "notebooklm_url": session.notebooklm_url,
    }


@router.post("/api/sessions/{session_id}/knowledge/regenerate", dependencies=[Depends(require_admin)])
async def regenerate_knowledge(session_id: str, request: Request) -> dict:
    session = request.app.state.manager.regenerate(session_id)
    return session.info()


@router.post("/api/sessions/{session_id}/ask")
async def ask_talk(session_id: str, body: AskBody, request: Request) -> dict:
    settings = request.app.state.settings
    session = request.app.state.manager.get(session_id)
    if session is None:
        raise HTTPException(404, "sala no encontrada")
    if session.running:
        raise HTTPException(409, "la charla todavía no terminó")
    if not settings.gemini_api_key:
        raise HTTPException(503, "las preguntas no están habilitadas en este servidor")
    question = body.q.strip()
    if not question:
        raise HTTPException(400, "la pregunta está vacía")

    cache = request.app.state.ask_cache
    cache_key = (session_id, normalize_question(question))
    cached = cache.get(cache_key)
    if cached is not None:
        return {"answer": cached, "cached": True}
    if not request.app.state.ask_limiter.allow(client_ip(request)):
        raise HTTPException(429, "Llegaste al límite de preguntas, probá en unos minutos")

    events = load_captions(session.captions_path) if session.captions_path else []
    transcript = knowledge.source_transcript(session.meta(), events)
    if not transcript:
        raise HTTPException(409, "esta charla no tiene transcripción")
    try:
        client = knowledge.get_client(settings.gemini_api_key)
        answer = await knowledge.ask(client, settings.kp_model, session.meta(), transcript, question)
    except Exception as e:
        if knowledge.is_overloaded(e):
            raise HTTPException(429, "Mucha demanda, probá en un minuto")
        session.log.warning("ask failed: %s: %s", type(e).__name__, e)
        raise HTTPException(502, "no se pudo responder, probá de nuevo")
    cache.put(cache_key, answer)
    return {"answer": answer, "cached": False}


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
