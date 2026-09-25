"""Session files under DATA_DIR/sessions/<id>/ (T2.3)."""

import asyncio
import json
import logging
from pathlib import Path

_log = logging.getLogger("backend.persistence")


class CaptionWriter:
    """Appends final captions to captions.jsonl from its own task.

    Every room shares one event loop, so a blocking write would stall all of them: put() only
    enqueues, and the actual append + flush runs in a thread (asyncio.to_thread)."""

    def __init__(self, path: Path, log: logging.Logger | logging.LoggerAdapter | None = None):
        self.path = path
        self.log = log or _log
        self.written = 0
        self.write_errors = 0
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"writer:{self.path.parent.name}")

    def put(self, msg: dict) -> None:
        self._queue.put_nowait(msg)

    async def close(self) -> None:
        """Write everything queued so far, then stop."""
        if self._task is None or self._task.done():
            return
        self._queue.put_nowait(None)
        await asyncio.shield(self._task)

    async def _run(self) -> None:
        while True:
            batch = [await self._queue.get()]
            while not self._queue.empty():
                batch.append(self._queue.get_nowait())
            lines = [msg for msg in batch if msg is not None]
            if lines:
                try:
                    await asyncio.to_thread(self._append, lines)
                    self.written += len(lines)
                except OSError as e:  # disk full, permissions...: log it, never take the room down
                    self.write_errors += 1
                    self.log.error("captions.jsonl write failed: %s", e)
            if None in batch:
                return

    def _append(self, lines: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write("".join(json.dumps(msg, ensure_ascii=False) + "\n" for msg in lines))
            f.flush()


class MetaWriter:
    """Overwrites meta.json with the latest snapshot handed to put(), from its own task.

    Same producer/consumer shape as CaptionWriter (never block the room on disk), but a
    snapshot write only needs the *last* queued value per drain cycle, not every line."""

    def __init__(self, path: Path, log: logging.Logger | logging.LoggerAdapter | None = None):
        self.path = path
        self.log = log or _log
        self.written = 0
        self.write_errors = 0
        self._queue: asyncio.Queue[dict | None] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name=f"meta:{self.path.parent.name}")

    def put(self, meta: dict) -> None:
        self._queue.put_nowait(meta)

    async def close(self) -> None:
        if self._task is None or self._task.done():
            return
        self._queue.put_nowait(None)
        await asyncio.shield(self._task)

    async def _run(self) -> None:
        while True:
            batch = [await self._queue.get()]
            while not self._queue.empty():
                batch.append(self._queue.get_nowait())
            latest = next((msg for msg in reversed(batch) if msg is not None), None)
            if latest is not None:
                try:
                    await asyncio.to_thread(self._write, latest)
                    self.written += 1
                except OSError as e:
                    self.write_errors += 1
                    self.log.error("meta.json write failed: %s", e)
            if None in batch:
                return

    def _write(self, meta: dict) -> None:
        write_json(self.path, meta)


def write_json(path: Path, data: dict) -> None:
    """Write via a temp file + rename, so a reader never sees a half-written file.
    Blocking: call it from asyncio.to_thread inside the event loop."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_json(path: Path) -> dict | None:
    """Read a JSON file written by write_json (None if missing or malformed)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def load_all_meta(data_dir: Path) -> list[dict]:
    """Read DATA_DIR/sessions/*/meta.json, skipping missing or malformed files."""
    sessions_dir = Path(data_dir) / "sessions"
    if not sessions_dir.is_dir():
        return []
    metas = []
    for meta_path in sorted(sessions_dir.glob("*/meta.json")):
        try:
            metas.append(json.loads(meta_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as e:
            _log.warning("skipping malformed %s: %s", meta_path, e)
    return metas


def load_captions(path: Path) -> list[dict]:
    """Read every final caption line from captions.jsonl (for exports/reload), skipping bad lines."""
    if not Path(path).exists():
        return []
    captions = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            captions.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return captions
