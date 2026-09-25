"""FastAPI: rutas, static, lifespan."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.api import sessions, ws
from backend.api.errors import capacity_error_handler
from backend.config import Settings, configure_logging, get_settings
from backend.core.capacity import CapacityError
from backend.core.loop_monitor import LoopLagMonitor
from backend.core.manager import SessionManager

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

log = logging.getLogger("backend.app")


def seed_demo(manager: SessionManager, settings: Settings) -> None:
    """Demo room created at startup, until the operator console exists (T2.9).
    ENGINE=replay always gets DEMO_ROOMS of them (no API usage, used by the audience load test);
    other engines get one, only with DEMO_FILE."""
    if settings.engine == "replay":
        for i in range(max(1, settings.demo_rooms)):
            title = "Demo" if i == 0 else f"Demo {i + 1}"
            manager.start(manager.create(title, speaker="Replay de ejemplo", source_lang="en").id)
    elif settings.demo_file:
        session = manager.create(
            "Demo",
            speaker=Path(settings.demo_file).stem,
            source_lang=settings.demo_lang,
            file=settings.demo_file,
            loop=settings.demo_loop,
        )
        manager.start(session.id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    app.state.settings = settings
    app.state.manager = SessionManager(settings)
    app.state.loop_monitor = LoopLagMonitor()
    app.state.loop_monitor.start()
    try:
        seed_demo(app.state.manager, settings)
    except Exception as e:  # the room is already in ERROR with the reason; keep serving
        log.warning("demo room could not start: %s: %s", type(e).__name__, e)
    log.info("ready: engine=%s", settings.engine)
    yield
    await app.state.manager.stop_all()
    await app.state.loop_monitor.stop()


app = FastAPI(title="Nerdearla Live Captions", lifespan=lifespan)
app.add_exception_handler(CapacityError, capacity_error_handler)
app.include_router(sessions.router)
app.include_router(ws.router)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")  # last: catch-all
