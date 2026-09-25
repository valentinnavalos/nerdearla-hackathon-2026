"""SessionManager: registry of rooms + pub/sub entry point for the API/WS layer."""

import asyncio
from pathlib import Path
from typing import Callable

from backend.config import DEFAULT_GLOSSARY_PATH, Settings
from backend.core.glossary import Glossary
from backend.core.persistence import load_all_meta
from backend.core.session import LANGS, Session, SessionStatus, slugify
from backend.engine.base import Engine
from backend.engine.factory import create_engine


class SessionNotFound(KeyError):
    pass


class CapacityError(RuntimeError):
    """No free Gemini Live slot: the room is not started (the API answers 409, T2.5)."""


class SessionManager:
    def __init__(
        self,
        settings: Settings,
        engine_factory: Callable[[], Engine] | None = None,
        default_glossary: Glossary | None = None,
    ):
        self.settings = settings
        self._engine_factory = engine_factory or (lambda: create_engine(settings))
        if default_glossary is None and Path(DEFAULT_GLOSSARY_PATH).exists():
            default_glossary = Glossary.load(DEFAULT_GLOSSARY_PATH)
        self.default_glossary = default_glossary or Glossary()
        self._sessions: dict[str, Session] = {}
        self._live_rooms: set[str] = set()  # rooms holding a Live slot, for their whole run

    def create(
        self,
        title: str,
        speaker: str = "",
        source_lang: str = "en",
        source: str = "file",
        file: str | None = None,
        loop: bool = False,
        glossary_text: str | None = None,
    ) -> Session:
        if source_lang not in LANGS:
            raise ValueError(f"source_lang debe ser uno de {LANGS}")
        if source not in ("file", "mic"):
            raise ValueError("source debe ser 'file' o 'mic'")
        session_glossary = Glossary.parse_text(glossary_text) if glossary_text else None
        session_id = self._unique_id(slugify(title))
        session = Session(
            id=session_id,
            title=title,
            speaker=speaker,
            source_lang=source_lang,
            source=source,
            file=file,
            loop=loop,
            glossary=Glossary.merge(self.default_glossary, session_glossary),
            realtime=self.settings.realtime,
            captions_path=self._captions_path(session_id),
            meta_path=self._meta_path(session_id),
        )
        self._sessions[session.id] = session
        return session

    def _captions_path(self, session_id: str) -> Path:
        return Path(self.settings.data_dir) / "sessions" / session_id / "captions.jsonl"

    def _meta_path(self, session_id: str) -> Path:
        return Path(self.settings.data_dir) / "sessions" / session_id / "meta.json"

    def reload(self) -> None:
        """Bring back rooms that finished in a previous process (T2.3): only STOPPED/ERROR
        rooms are restored (a RUNNING room's Live session died with the old process)."""
        for meta in load_all_meta(self.settings.data_dir):
            session_id = meta.get("id")
            if not session_id or session_id in self._sessions:
                continue
            if meta.get("status") not in (SessionStatus.STOPPED.value, SessionStatus.ERROR.value):
                continue
            session = Session.from_meta(meta, self._captions_path(session_id), self._meta_path(session_id))
            self._sessions[session.id] = session

    def _unique_id(self, base: str) -> str:
        candidate, n = base, 2
        while candidate in self._sessions:
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFound(session_id)
        return session

    def list(self) -> list[Session]:
        return list(self._sessions.values())

    def start(self, session_id: str) -> Session:
        session = self.require(session_id)
        try:
            engine = self._engine_factory()
        except Exception as e:
            session.fail(f"{type(e).__name__}: {e}")
            raise
        if engine.uses_live:
            # capacity guard: reject instead of queueing; a room keeps its slot through rotations
            usage = self.live_usage()
            if session.id not in self._live_rooms and usage["used"] >= usage["max"]:
                raise CapacityError(
                    f"cupo Live lleno ({usage['used']}/{usage['max']}): pará otra sala o subí MAX_CONCURRENT_LIVE"
                )
        session.start(engine)
        if engine.uses_live:
            self._live_rooms.add(session.id)
            session.on_done(lambda: self._release_slot(session))
        return session

    def _release_slot(self, session: Session) -> None:
        if not session.running:  # a quick restart may already hold the slot again
            self._live_rooms.discard(session.id)

    def live_usage(self) -> dict[str, int]:
        """Live slots in use vs MAX_CONCURRENT_LIVE (for the panel, T3.2)."""
        return {"used": len(self._live_rooms), "max": self.settings.max_concurrent_live}

    async def stop(self, session_id: str) -> Session:
        session = self.require(session_id)
        await session.stop()
        return session

    async def delete(self, session_id: str) -> None:
        await self.stop(session_id)
        del self._sessions[session_id]

    async def stop_all(self) -> None:
        await asyncio.gather(*(s.stop() for s in self._sessions.values()), return_exceptions=True)

    def subscribe(self, session_id: str, lang: str) -> asyncio.Queue:
        return self.require(session_id).subscribe(lang)

    def unsubscribe(self, session_id: str, lang: str, queue: asyncio.Queue) -> None:
        session = self.get(session_id)
        if session is not None:
            session.unsubscribe(lang, queue)
