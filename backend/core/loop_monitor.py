"""Event-loop lag: every room, writer and WS client shares one loop, so anything that blocks it
(a sync write, a heavy json.dumps, a slow callback) delays all of them. A ticker that expects to
wake every `interval` seconds measures by how much it wakes up late."""

import asyncio
import time
from collections import deque

WINDOW_SAMPLES = 6000  # 10 min at 100 ms


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


class LoopLagMonitor:
    def __init__(self, interval: float = 0.1):
        self.interval = interval
        self._samples: deque[tuple[float, float]] = deque(maxlen=WINDOW_SAMPLES)  # (monotonic, lag_ms)
        self._task: asyncio.Task | None = None
        self.count = 0
        self.lag_ms_max = 0.0
        self.over_50ms = 0
        self.over_100ms = 0

    def start(self) -> None:
        self._task = asyncio.create_task(self._run(), name="loop-lag-monitor")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _run(self) -> None:
        while True:
            expected = time.monotonic() + self.interval
            await asyncio.sleep(self.interval)
            now = time.monotonic()
            self.record(now, max(0.0, (now - expected) * 1000))

    def record(self, at: float, lag_ms: float) -> None:
        self._samples.append((at, lag_ms))
        self.count += 1
        self.lag_ms_max = max(self.lag_ms_max, lag_ms)
        self.over_50ms += lag_ms > 50
        self.over_100ms += lag_ms > 100

    def reset(self) -> None:
        """Start a fresh measurement (the probes reset it between trials)."""
        self._samples.clear()
        self.count = 0
        self.lag_ms_max = 0.0
        self.over_50ms = self.over_100ms = 0

    def stats(self, window_s: float | None = None) -> dict:
        """Lag percentiles over the last `window_s` seconds (all kept samples when None)."""
        if window_s is None:
            lags = [lag for _, lag in self._samples]
        else:
            since = time.monotonic() - window_s
            lags = [lag for at, lag in self._samples if at >= since]
        return {
            "samples": len(lags),
            "lag_ms_p50": round(_percentile(lags, 0.50), 1),
            "lag_ms_p99": round(_percentile(lags, 0.99), 1),
            "lag_ms_max": round(max(lags, default=0.0), 1),
            "over_50ms": sum(lag > 50 for lag in lags),
            "over_100ms": sum(lag > 100 for lag in lags),
        }
