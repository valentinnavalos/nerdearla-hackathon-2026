from dataclasses import dataclass
from typing import AsyncIterator

from backend.sources.base import BYTES_PER_SAMPLE, SAMPLE_RATE, AudioFrame


@dataclass
class Chunk:
    index: int
    pcm: bytes
    t_capture: float  # capture time of the chunk's last frame (when it became ready)


async def chunk_frames(
    frames: AsyncIterator[AudioFrame],
    chunk_seconds: float = 5.0,
    overlap_seconds: float = 0.75,
) -> AsyncIterator[Chunk]:
    """Group frames into fixed-size chunks, carrying an overlap tail into the next one."""
    chunk_bytes = int(chunk_seconds * SAMPLE_RATE) * BYTES_PER_SAMPLE
    overlap_bytes = int(overlap_seconds * SAMPLE_RATE) * BYTES_PER_SAMPLE
    buf = bytearray()
    index = 0
    fresh = 0  # bytes in buf not yet emitted in a previous chunk
    async for frame in frames:
        buf += frame.pcm
        fresh += len(frame.pcm)
        if len(buf) >= chunk_bytes:
            yield Chunk(index, bytes(buf), frame.t_capture)
            index += 1
            buf = bytearray(buf[-overlap_bytes:]) if overlap_bytes else bytearray()
            fresh = 0
    if fresh > 0 and len(buf) > 0:
        yield Chunk(index, bytes(buf), frame.t_capture)
