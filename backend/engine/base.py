from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable

from backend.core.events import CaptionEvent
from backend.sources.base import AudioFrame

Emit = Callable[[CaptionEvent], Awaitable[None]]


@dataclass
class SessionContext:
    """Datos de la sala que el Engine necesita para procesar audio."""

    session_id: str
    source_lang: str
    target_lang: str
    glossary: Any | None = None  # backend.core.glossary.Glossary (T1.7)
    metrics: Any | None = None  # backend.core.metrics (T2.4)


class Engine(ABC):
    """Common contract for every transcription/translation engine."""

    @abstractmethod
    async def run(self, frames: AsyncIterator[AudioFrame], emit: Emit, ctx: SessionContext) -> None:
        """Consume audio frames until the source ends, calling emit() for each caption."""
