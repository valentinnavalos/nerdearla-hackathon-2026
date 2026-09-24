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
