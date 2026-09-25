"""MicSource: fed by push() from /ws/ingest/{id} (T2.6), instead of a producer task."""

import time

from backend.sources.base import AudioFrame, AudioSource, FrameQueue

MIC_QUEUE_SIZE = 50  # 5 s of 100 ms frames


class MicSource(AudioSource):
    """AudioSource whose frames come from push() calls made by the ingest WS handler,
    not from an internal producer task. Reuses FrameQueue for the drop-oldest-when-full
    behavior and dropped_frames counting already used by every other source."""

    def __init__(self, maxsize: int = MIC_QUEUE_SIZE):
        self._queue = FrameQueue(maxsize=maxsize)
        self.connected = False
        self.last_push_at: float | None = None

    @property
    def dropped_frames(self) -> int:
        return self._queue.dropped_frames

    def push(self, pcm: bytes) -> None:
        self.last_push_at = time.monotonic()
        self.connected = True
        self._queue.put(AudioFrame(pcm=pcm, t_capture=self.last_push_at))

    def close(self) -> None:
        self.connected = False
        self._queue.close()

    def frames(self):
        return self._queue.__aiter__()

    def __aiter__(self):
        """Session._run passes a MicSource directly as `frames` to the engine (no
        producer task, since push() is called externally by the ingest WS), so it must
        itself be iterable the same way FrameQueue is."""
        return self._queue.__aiter__()

    def is_connected(self, timeout_s: float = 3.0) -> bool:
        if self.last_push_at is None:
            return False
        return (time.monotonic() - self.last_push_at) < timeout_s
