"""In-memory limits for the public "Preguntale a la charla" endpoint (T3.6).

One process serves every room, so a dict is enough; a restart simply resets the counters."""

import re
import time
import unicodedata
from collections import OrderedDict, deque
from typing import Callable

from fastapi import Request


def client_ip(request: Request) -> str:
    """The client's IP behind Render's proxy: the proxy *appends* the address it saw to
    X-Forwarded-For, so the last entry is the one a client cannot spoof."""
    forwarded = request.headers.get("x-forwarded-for", "")
    hops = [h.strip() for h in forwarded.split(",") if h.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "unknown"


def normalize_question(q: str) -> str:
    """Lowercase, no accents or punctuation, collapsed spaces: the cache key for a question."""
    ascii_q = unicodedata.normalize("NFKD", q).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^\w\s]", " ", ascii_q).split())


class RateLimiter:
    """Sliding window: at most `limit` hits per key in the last `window_s` seconds."""

    def __init__(self, limit: int, window_s: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


class LRUCache:
    def __init__(self, max_size: int = 500):
        self.max_size = max_size
        self._data: OrderedDict = OrderedDict()

    def get(self, key):
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, key, value) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)
