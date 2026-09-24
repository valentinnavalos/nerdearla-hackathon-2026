import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator

SAMPLE_RATE = 16000  # Hz, mono, s16le
BYTES_PER_SAMPLE = 2


@dataclass
class AudioFrame:
    pcm: bytes  # 16kHz mono s16le
    t_capture: float  # time.monotonic() when the audio was captured/emitted


class AudioSource(ABC):
    """Common contract for every audio input (file, mic, stream...)."""

    @abstractmethod
    def frames(self) -> AsyncIterator[AudioFrame]:
        """Yield normalized PCM frames until the source ends."""


class FrameQueue:
    """Bounded buffer between a source (producer) and an engine (consumer).
    put() never blocks: when full, the oldest frame is dropped so a slow engine
    can't stall the live pacing of the source."""

    def __init__(self, maxsize: int = 50):
        self._queue: asyncio.Queue[AudioFrame | None] = asyncio.Queue(maxsize=maxsize)
        self.dropped_frames = 0

    def _put(self, item: AudioFrame | None) -> None:
        if self._queue.full():
            dropped = self._queue.get_nowait()
            if dropped is not None:
                self.dropped_frames += 1
        self._queue.put_nowait(item)

    def put(self, frame: AudioFrame) -> None:
        self._put(frame)

    def close(self) -> None:
        """Signal end of stream to the consumer."""
        self._put(None)

    async def __aiter__(self) -> AsyncIterator[AudioFrame]:
        while True:
            frame = await self._queue.get()
            if frame is None:
                return
            yield frame


async def pump(source: AudioSource, queue: FrameQueue) -> None:
    """Producer task: move frames from the source into the queue, then close it."""
    try:
        async for frame in source.frames():
            queue.put(frame)
    finally:
        queue.close()
