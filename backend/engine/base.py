from abc import ABC, abstractmethod
from typing import AsyncIterator, Awaitable, Callable

from backend.core.events import CaptionEvent
from backend.sources.base import AudioFrame

Emit = Callable[[CaptionEvent], Awaitable[None]]


class Engine(ABC):
    """Common contract for every transcription/translation engine."""

    @abstractmethod
    async def run(self, frames: AsyncIterator[AudioFrame], emit: Emit) -> None:
        """Consume audio frames until the source ends, calling emit() for each caption."""
