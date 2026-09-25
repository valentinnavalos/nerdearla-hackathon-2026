"""Session (stage worker): one room = source -> FrameQueue -> engine -> emit -> subscribers."""

import asyncio
import logging
import re
import time
import unicodedata
from collections import deque
from enum import Enum
from pathlib import Path
from typing import Callable

from backend.core.events import CaptionEvent
from backend.core.glossary import Glossary
from backend.core.metrics import SessionMetrics
from backend.core.persistence import CaptionWriter, MetaWriter, load_captions, write_json
from backend.engine.base import Engine, SessionContext
from backend.sources.base import FrameQueue, pump
from backend.sources.file_source import FileSource
from backend.sources.mic_source import MicSource

LANGS = ("en", "es")
HISTORY_SIZE = 50  # finals kept per language for late joiners
SUBSCRIBER_QUEUE_SIZE = 100
FRAME_QUEUE_SIZE = 50  # 5 s of audio
KP_STATUSES = ("pending", "ready", "error")  # Knowledge Pack generation after Stop (T3.4)


class SessionStatus(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    ROTATING = "ROTATING"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-") or "sala"


def other_lang(lang: str) -> str:
    return "es" if lang == "en" else "en"


async def _no_frames():
    return
    yield


class Session:
    def __init__(
        self,
        id: str,
        title: str,
        speaker: str,
        source_lang: str,
        source: str = "file",
        file: str | None = None,
        loop: bool = False,
        glossary: Glossary | None = None,
        realtime: bool = True,
        captions_path: Path | None = None,  # finals are appended here (T2.3)
        meta_path: Path | None = None,  # room snapshot for reload-on-restart (T2.3)
        engine_name: str = "",
    ):
        self.id = id
        self.title = title
        self.speaker = speaker
        self.source_lang = source_lang
        self.target_lang = other_lang(source_lang)
        self.source = source
        self.file = file
        self.loop = loop
        self.glossary = glossary or Glossary()
        self.realtime = realtime
        self.captions_path = captions_path
        self.meta_path = meta_path
        self.engine_name = engine_name
        self.status = SessionStatus.CREATED
        self.started_at: float | None = None
        self.stopped_at: float | None = None
        self.last_error: str | None = None
        self.kp_status: str | None = None  # None until the post-talk pipeline runs (T3.4)
        self.notebooklm_url: str | None = None  # set by the optional exporter (T3.9)
        self.events = 0
        self._frames: FrameQueue | None = None
        self._mic_source: MicSource | None = None
        self._history: dict[str, deque[dict]] = {lang: deque(maxlen=HISTORY_SIZE) for lang in LANGS}
        self._subscribers: dict[str, set[asyncio.Queue]] = {lang: set() for lang in LANGS}
        self._task: asyncio.Task | None = None
        self._writer: CaptionWriter | None = None
        self._meta_writer: MetaWriter | None = None
        self._engine: Engine | None = None
        self._ctx: SessionContext | None = None
        self.log = logging.LoggerAdapter(logging.getLogger("backend.session"), {"session": id})

    def meta(self) -> dict:
        """Snapshot persisted to meta.json (T2.3), plus the post-talk state (T3.4, T3.9)."""
        return {
            "id": self.id,
            "title": self.title,
            "speaker": self.speaker,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "source": self.source,
            "file": self.file,
            "loop": self.loop,
            "engine": self.engine_name,
            "glossary": self.glossary.to_dict() if self.glossary else None,
            "status": self.status.value,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_error": self.last_error,
            "kp_status": self.kp_status,
            "notebooklm_url": self.notebooklm_url,
        }

    @property
    def knowledge_path(self) -> Path | None:
        return self.meta_path.parent / "knowledge.json" if self.meta_path else None

    def save_meta(self) -> None:
        """Rewrite meta.json once the run is over (the MetaWriter is already closed).
        Blocking: call it from asyncio.to_thread."""
        if self.meta_path is not None:
            write_json(self.meta_path, self.meta())

    @classmethod
    def from_meta(cls, meta: dict, captions_path: Path, meta_path: Path) -> "Session":
        """Rebuild a finished room from its meta.json + captions.jsonl for reload-on-restart (T2.3).
        Reload never resumes a RUNNING room - a dead process can't reconnect a Live session."""
        session = cls(
            id=meta["id"],
            title=meta.get("title", meta["id"]),
            speaker=meta.get("speaker", ""),
            source_lang=meta.get("source_lang", "en"),
            source=meta.get("source", "file"),
            file=meta.get("file"),
            loop=meta.get("loop", False),
            glossary=Glossary(**meta["glossary"]) if meta.get("glossary") else None,
            captions_path=captions_path,
            meta_path=meta_path,
            engine_name=meta.get("engine", ""),
        )
        status = meta.get("status")
        session.status = SessionStatus(status) if status in (SessionStatus.STOPPED.value, SessionStatus.ERROR.value) \
            else SessionStatus.STOPPED
        session.started_at = meta.get("started_at")
        session.stopped_at = meta.get("stopped_at")
        session.last_error = meta.get("last_error")
        kp_status = meta.get("kp_status")
        # "pending" means the process died mid-generation: nothing is running it anymore
        session.kp_status = "error" if kp_status == "pending" else (kp_status if kp_status in KP_STATUSES else None)
        session.notebooklm_url = meta.get("notebooklm_url")
        for msg in load_captions(captions_path):
            lang = msg.get("lang")
            if lang in LANGS:
                session._history[lang].append(msg)
                session.events += 1
        return session

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def dropped_frames(self) -> int:
        if self._mic_source is not None:
            return self._mic_source.dropped_frames
        return self._frames.dropped_frames if self._frames else 0

    def push_audio(self, pcm: bytes) -> None:
        """Feed one 100ms PCM16 16kHz mono frame from the ingest WS (T2.6)."""
        if self._mic_source is not None:
            self._mic_source.push(pcm)

    def mic_connected(self, timeout_s: float = 3.0) -> bool:
        return self._mic_source is not None and self._mic_source.is_connected(timeout_s)

    def listeners(self) -> dict[str, int]:
        return {lang: len(subs) for lang, subs in self._subscribers.items()}

    def public_info(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "speaker": self.speaker,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "status": self.status.value,
            "kp_status": self.kp_status,
        }

    def info(self) -> dict:
        """Full state for the admin API / panel (T2.5, T3.2)."""
        return {
            **self.public_info(),
            "source": self.source,
            "file": self.file,
            "loop": self.loop,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_error": self.last_error,
            "uptime_s": (time.time() - self.started_at) if self.running and self.started_at else None,
            "mic_connected": self.mic_connected() if self.source == "mic" else None,
            "metrics": {
                "events": self.events,
                "dropped_frames": self.dropped_frames,
                "listeners": self.listeners(),
                "captions_written": self._writer.written if self._writer else 0,
                "write_errors": self._writer.write_errors if self._writer else 0,
                "runner": self._runner_stats(),
                "audio": self._ctx.metrics.snapshot() if self._ctx and self._ctx.metrics else None,
            },
        }

    def _runner_stats(self) -> dict | None:
        runner = getattr(self._engine, "runner", None)
        return dict(runner.stats) if runner is not None else None

    # --- lifecycle -----------------------------------------------------------

    def start(self, engine: Engine) -> None:
        if self.running:
            raise RuntimeError(f"la sala {self.id} ya está corriendo")
        if engine.needs_audio:
            if self.source == "mic":
                self._mic_source = MicSource()
            elif not self.file:
                raise ValueError("la fuente file necesita un archivo")
        self.status = SessionStatus.RUNNING
        self.started_at = time.time()
        self.stopped_at = None
        self.last_error = None
        self.engine_name = type(engine).__name__
        self._publish_status()
        if self.captions_path is not None:
            self._writer = CaptionWriter(self.captions_path, self.log)
            self._writer.start()
        if self.meta_path is not None:
            self._meta_writer = MetaWriter(self.meta_path, self.log)
            self._meta_writer.start()
            self._meta_writer.put(self.meta())
        self._task = asyncio.create_task(self._run(engine), name=f"session:{self.id}")

    def on_done(self, callback: Callable[[], None]) -> None:
        """Run `callback` when the current run ends, however it ends (used to free the Live slot)."""
        self._task.add_done_callback(lambda _: callback())

    async def _run(self, engine: Engine) -> None:
        ctx = SessionContext(self.id, self.source_lang, self.target_lang, self.glossary, metrics=SessionMetrics())
        self._ctx = ctx
        producer: asyncio.Task | None = None
        watcher: asyncio.Task | None = None
        self._engine = engine
        try:
            frames = _no_frames()
            if engine.needs_audio:
                if self.source == "mic":
                    frames = self._mic_source
                else:
                    self._frames = FrameQueue(maxsize=FRAME_QUEUE_SIZE)
                    source = FileSource(self.file, realtime=self.realtime, loop=self.loop)
                    producer = asyncio.create_task(pump(source, self._frames))
                    frames = self._frames
            source_desc = (self.file or self.source) if engine.needs_audio else "-"
            self.log.info("started: engine=%s source=%s", type(engine).__name__, source_desc)
            if getattr(engine, "uses_live", False):
                watcher = asyncio.create_task(self._watch_runner_state(engine))
            await engine.run(frames, self.emit, ctx)
            if producer and producer.done() and not producer.cancelled() and producer.exception():
                raise producer.exception()
            self._finish(SessionStatus.STOPPED)
        except asyncio.CancelledError:
            self._finish(SessionStatus.STOPPED)
            raise
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            self.log.exception("failed")
            self._finish(SessionStatus.ERROR)
        finally:
            if producer:
                producer.cancel()
            if watcher:
                watcher.cancel()
            if self._mic_source is not None:
                self._mic_source.close()
            if self._writer is not None:
                await self._writer.close()
            if self._meta_writer is not None:
                self._meta_writer.put(self.meta())
                await self._meta_writer.close()

    async def _watch_runner_state(self, engine: Engine) -> None:
        """Mirror LiveSessionRunner's rotation state (T2.1) into Session.status so
        subscribers see ROTATING/RECONNECTING without touching the frozen Engine ABC."""
        last_state = None
        while True:
            runner = getattr(engine, "runner", None)
            state = runner.stats.get("state") if runner and runner.stats else None
            if state and state != last_state and self.status not in (
                SessionStatus.STOPPED, SessionStatus.ERROR
            ):
                mapped = {
                    "RUNNING": SessionStatus.RUNNING,
                    "ROTATING": SessionStatus.ROTATING,
                    "RECONNECTING": SessionStatus.RECONNECTING,
                }.get(state)
                if mapped is not None and mapped != self.status:
                    self.status = mapped
                    self._publish_status()
                last_state = state
            await asyncio.sleep(0.5)

    async def stop(self) -> None:
        if self.running:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        if self._writer is not None:
            await self._writer.close()  # also when the task was cancelled before it ever ran
        if self.status not in (SessionStatus.STOPPED, SessionStatus.ERROR):
            self._finish(SessionStatus.STOPPED)

    def fail(self, error: str) -> None:
        """Mark the room as failed without running it (e.g. the engine could not be built)."""
        self.last_error = error
        self.log.error("cannot start: %s", error)
        self._finish(SessionStatus.ERROR)

    def _finish(self, status: SessionStatus) -> None:
        self.status = status
        self.stopped_at = time.time()
        self.log.info("%s (events=%d, dropped_frames=%d)", status.value, self.events, self.dropped_frames)
        self._publish_status()

    # --- pub/sub -------------------------------------------------------------

    async def emit(self, event: CaptionEvent) -> None:
        self.events += 1
        msg = event.model_dump()
        if event.final:
            self._history[event.lang].append(msg)
            if self._writer is not None:
                self._writer.put(msg)  # never awaits the disk
        self._publish(event.lang, msg)

    def history(self, lang: str) -> list[dict]:
        return list(self._history[lang])

    def subscribe(self, lang: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        self._subscribers[lang].add(queue)
        return queue

    def unsubscribe(self, lang: str, queue: asyncio.Queue) -> None:
        self._subscribers[lang].discard(queue)

    def _publish(self, lang: str, msg: dict) -> None:
        for queue in self._subscribers[lang]:
            if queue.full():
                queue.get_nowait()  # slow client: drop its oldest message, never block the room
            queue.put_nowait(msg)

    def _publish_status(self) -> None:
        msg = {"type": "session_status", "session_id": self.id, "status": self.status.value}
        for lang in LANGS:
            self._publish(lang, msg)
