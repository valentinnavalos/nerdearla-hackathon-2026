"""Session files under DATA_DIR/sessions/<id>/ (T2.3). meta.json and reloading on restart: pending."""

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
