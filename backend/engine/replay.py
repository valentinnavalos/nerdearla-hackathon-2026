import asyncio
import json
import time
from pathlib import Path
from typing import AsyncIterable

from backend.core.events import CaptionEvent
from backend.engine.base import Emit, Engine, SessionContext
from backend.sources.base import AudioFrame

LOOP_PAUSE_S = 2.0


class ReplayEngine(Engine):
    """Re-emits a captions.jsonl at its original pace: develops the front, records the
    video and lets anyone try the app without an API key."""

    needs_audio = False

    def __init__(self, path: str, loop: bool = True):
        self.path = path
        self.loop = loop

    def _load(self) -> list[dict]:
        lines = Path(self.path).read_text().splitlines()
        events = [json.loads(line) for line in lines if line.strip()]
        # paced on t1, not t0: every interim of a segment shares t0, t1 is when its text was known
        return sorted(events, key=lambda e: e["t1"])

    async def run(self, frames: AsyncIterable[AudioFrame], emit: Emit, ctx: SessionContext) -> None:
        events = self._load()
        if not events:
            return
        base = events[0]["t1"]
        lap_s = events[-1]["t1"] - base + LOOP_PAUSE_S
        lap_segs = max(e["seg"] for e in events) + 1
        t_start = time.monotonic()
        lap = 0
        while True:
            offset = lap * lap_s
            for e in events:
                delay = t_start + offset + (e["t1"] - base) - time.monotonic()
                if delay > 0:
                    await asyncio.sleep(delay)
                # shift seg and times on every lap so the front never sees a repeated segment
                await emit(CaptionEvent(**{
                    **e,
                    "session_id": ctx.session_id,
                    "seg": e["seg"] + lap * lap_segs,
                    "t0": e["t0"] + offset,
                    "t1": e["t1"] + offset,
                }))
            if not self.loop:
                return
            lap += 1
