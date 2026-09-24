import asyncio
import time
from typing import AsyncIterator

from backend.pipeline.normalize import normalize_file
from backend.sources.base import BYTES_PER_SAMPLE, SAMPLE_RATE, AudioFrame, AudioSource

FRAME_SECONDS = 0.1


class FileSource(AudioSource):
    """Reads an audio file; with realtime=True paces frames like a live stream."""

    def __init__(self, path: str, realtime: bool = True, loop: bool = False):
        self.path = path
        self.realtime = realtime
        self.loop = loop

    async def frames(self) -> AsyncIterator[AudioFrame]:
        pcm = await normalize_file(self.path)
        size = int(SAMPLE_RATE * FRAME_SECONDS) * BYTES_PER_SAMPLE
        while True:
            t_start = time.monotonic()
            n = 0
            for i in range(0, len(pcm), size):
                if self.realtime:
                    target = t_start + n * FRAME_SECONDS
                    delay = target - time.monotonic()
                    if delay > 0:
                        await asyncio.sleep(delay)
                n += 1
                yield AudioFrame(pcm=pcm[i:i + size], t_capture=time.monotonic())
            if not self.loop:
                return
