import asyncio
import time
from typing import AsyncIterator

from backend.pipeline.normalize import normalize_file
from backend.sources.base import BYTES_PER_SAMPLE, SAMPLE_RATE, AudioFrame, AudioSource

FRAME_SECONDS = 0.1


class FileSource(AudioSource):
    """Reads an audio file; with realtime=True paces frames like a live stream."""

    def __init__(self, path: str, realtime: bool = True):
        self.path = path
        self.realtime = realtime

    async def frames(self) -> AsyncIterator[AudioFrame]:
        pcm = await normalize_file(self.path)
        size = int(SAMPLE_RATE * FRAME_SECONDS) * BYTES_PER_SAMPLE
        for i in range(0, len(pcm), size):
            if self.realtime:
                await asyncio.sleep(FRAME_SECONDS)
            yield AudioFrame(pcm=pcm[i:i + size], t_capture=time.monotonic())
