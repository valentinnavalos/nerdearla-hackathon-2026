"""FastAPI: rutas, static, lifespan."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api import sessions, ws
from backend.config import Settings, configure_logging, get_settings
from backend.core.manager import CapacityError, SessionManager, SessionNotFound

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"

log = logging.getLogger("backend.app")


class SPAStaticFiles(StaticFiles):
    """Falls back to index.html on a 404 so React Router's client-side routes
    (e.g. /admin, /watch/<id>) resolve on a hard navigation/refresh, not just
    when reached via an in-app link."""

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


PITCH_ROOMS = [
    {
        "title": "Interview with Rob Pike",
        "speaker": "Rob Pike",
        "source_lang": "en",
        "file": "samples/en_talk_3min.mp3",
        "loop": True,
    },
    {
        "title": "Brownfield Engineering",
        "speaker": "Nicolás Páez",
        "source_lang": "es",
        "file": "samples/es_talk_2min.mp3",
        "loop": True,
    },
    {
        "title": "Human-Centric Engineering",
        "speaker": "Ben Popplestone",
        "source_lang": "en",
        "file": "samples/human-centric-eng-by-ben-popplestone.mp3",
        "loop": True,
    },
]


def seed_demo(manager: SessionManager, settings: Settings) -> None:
    """Pitch-ready rooms created at startup, until the operator console exists (T2.9).
    ENGINE=replay gets a single replay room (no API usage); other engines get the 3 PITCH_ROOMS."""
    if settings.engine == "replay":
        session = manager.create("Demo", speaker="Replay de ejemplo", source_lang="en")
        manager.start(session.id)
        return
    for room in PITCH_ROOMS:
        session = manager.create(
            room["title"],
            speaker=room["speaker"],
            source_lang=room["source_lang"],
            file=room["file"],
            loop=room["loop"],
        )
        manager.start(session.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.manager = SessionManager(settings)
    try:
        app.state.manager.reload()
    except Exception as e:  # a bad meta.json must never stop the app from starting
        log.warning("session reload failed: %s: %s", type(e).__name__, e)
    try:
        seed_demo(app.state.manager, settings)
    except Exception as e:  # the room is already in ERROR with the reason; keep serving
        log.warning("demo room could not start: %s: %s", type(e).__name__, e)
    log.info("ready: engine=%s", settings.engine)
    yield
    await app.state.manager.stop_all()


app = FastAPI(title="Nerdearla Live Captions", lifespan=lifespan)
app.include_router(sessions.router)
app.include_router(ws.router)


@app.exception_handler(SessionNotFound)
async def _not_found(request: Request, exc: SessionNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": f"session not found: {exc}"})


@app.exception_handler(CapacityError)
async def _capacity(request: Request, exc: CapacityError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def _bad_value(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


app.mount("/", SPAStaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")  # last: catch-all
