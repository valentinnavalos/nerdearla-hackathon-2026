import asyncio
import time

from backend.sources import file_source
from backend.sources.base import BYTES_PER_SAMPLE, SAMPLE_RATE, FrameQueue, pump
from backend.sources.file_source import FileSource


def _fake_pcm(seconds: float):
    async def normalize(_path: str) -> bytes:
        return b"\x00" * int(seconds * SAMPLE_RATE) * BYTES_PER_SAMPLE

    return normalize


def test_pacing_holds_with_slow_consumer(monkeypatch):
    monkeypatch.setattr(file_source, "normalize_file", _fake_pcm(3.0))

    async def main():
        queue = FrameQueue(maxsize=5)

        async def slow_engine():
            async for _ in queue:
                await asyncio.sleep(0.3)  # 3x slower than real time

        t0 = time.monotonic()
        consumer = asyncio.create_task(slow_engine())
        await pump(FileSource("x.mp3"), queue)
        elapsed = time.monotonic() - t0
        consumer.cancel()
        return elapsed, queue.dropped_frames

    elapsed, dropped = asyncio.run(main())
    assert 2.8 <= elapsed <= 3.2
    assert dropped > 0


def test_source_finishes_in_real_time(monkeypatch):
    monkeypatch.setattr(file_source, "normalize_file", _fake_pcm(3.0))

    async def main():
        queue = FrameQueue(maxsize=5)
        t0 = time.monotonic()
        await pump(FileSource("x.mp3"), queue)  # nobody consumes: the source must not wait
        return time.monotonic() - t0, queue.dropped_frames

    elapsed, dropped = asyncio.run(main())
    assert 2.8 <= elapsed <= 3.2
    assert dropped >= 30 - 5


def test_loop_restarts_the_file(monkeypatch):
    monkeypatch.setattr(file_source, "normalize_file", _fake_pcm(0.3))

    async def main():
        frames = []
        async for frame in FileSource("x.mp3", realtime=False, loop=True).frames():
            frames.append(frame)
            if len(frames) == 7:
                break
        return frames

    assert len(asyncio.run(main())) == 7
