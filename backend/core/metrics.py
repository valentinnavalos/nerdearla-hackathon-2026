"""Audio level, local VAD, latencies and quota (T2.4)."""

import json
import logging
import math
import sys
import time
from array import array
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

_log = logging.getLogger("backend.metrics")
_PACIFIC = ZoneInfo("America/Los_Angeles")  # matches Google's RPD reset (T2.4)

SILENCE_DBFS = -120.0
SILENCE_ALERT_DBFS = -50.0
SILENCE_ALERT_S = 20.0
VAD_DBFS = -45.0
VAD_HANGOVER_S = 0.3
LATENCY_WINDOW = 200


def rms_dbfs(pcm: bytes) -> float:
    """RMS level of a PCM16 LE frame in dBFS (0 = full scale)."""
    samples = array("h", pcm[: len(pcm) - len(pcm) % 2])
    if sys.byteorder == "big":
        samples.byteswap()
    if not samples:
        return SILENCE_DBFS
    mean_sq = sum(s * s for s in samples) / len(samples)
    if mean_sq == 0:
        return SILENCE_DBFS
    return 10 * math.log10(mean_sq / 32768**2)


class VoiceActivityDetector:
    """Local VAD: voice = level above threshold, with a hangover so a short dip
    mid-word doesn't count as the end of a voice segment."""

    def __init__(self, threshold_dbfs: float = VAD_DBFS, hangover_s: float = VAD_HANGOVER_S):
        self.threshold_dbfs = threshold_dbfs
        self.hangover_s = hangover_s
        self._voice = False
        self._last_above_t: float | None = None
        self._voice_start_t: float | None = None

    def process(self, level_dbfs: float, t: float) -> dict | None:
        """Feed one frame's level at time `t` (seconds, monotonic clock). Returns
        {"event": "start"|"end", "t": t} on a voice-segment transition, else None."""
        above = level_dbfs >= self.threshold_dbfs
        if above:
            self._last_above_t = t
            if not self._voice:
                self._voice = True
                self._voice_start_t = t
                return {"event": "start", "t": t}
            return None
        if self._voice and self._last_above_t is not None and t - self._last_above_t >= self.hangover_s:
            self._voice = False
            return {"event": "end", "t": t}
        return None

    @property
    def in_voice(self) -> bool:
        return self._voice


class SilenceAlert:
    """True once the level has stayed below SILENCE_ALERT_DBFS for SILENCE_ALERT_S."""

    def __init__(self, threshold_dbfs: float = SILENCE_ALERT_DBFS, hold_s: float = SILENCE_ALERT_S):
        self.threshold_dbfs = threshold_dbfs
        self.hold_s = hold_s
        self._quiet_since: float | None = None
        self.active = False

    def process(self, level_dbfs: float, t: float) -> bool:
        if level_dbfs >= self.threshold_dbfs:
            self._quiet_since = None
            self.active = False
        else:
            if self._quiet_since is None:
                self._quiet_since = t
            self.active = (t - self._quiet_since) >= self.hold_s
        return self.active


class LatencyTracker:
    """p50/p95 over the last `maxsize` samples, in milliseconds."""

    def __init__(self, maxsize: int = LATENCY_WINDOW):
        self._samples: deque[float] = deque(maxlen=maxsize)

    def add(self, ms: float) -> None:
        self._samples.append(ms)

    def _percentile(self, p: float) -> float | None:
        if not self._samples:
            return None
        values = sorted(self._samples)
        idx = min(len(values) - 1, int(round(p * (len(values) - 1))))
        return values[idx]

    def p50(self) -> float | None:
        return self._percentile(0.50)

    def p95(self) -> float | None:
        return self._percentile(0.95)


class SessionMetrics:
    """Aggregates everything above for one room; assigned to SessionContext.metrics."""

    def __init__(self):
        self.vad = VoiceActivityDetector()
        self.silence = SilenceAlert()
        self.first_partial_latency = LatencyTracker()
        self.final_latency = LatencyTracker()
        self.level_dbfs = SILENCE_DBFS
        self.last_frame_at: float | None = None  # session-relative t (for latency math)
        self._last_frame_wall: float | None = None  # absolute monotonic (for "age", T3.2)
        self._voice_start_t: float | None = None
        self._voice_end_t: float | None = None
        self._partial_since_voice = False

    def on_frame(self, pcm: bytes, t: float) -> None:
        self.level_dbfs = rms_dbfs(pcm)
        self.last_frame_at = t
        self._last_frame_wall = time.monotonic()
        self.silence.process(self.level_dbfs, t)
        event = self.vad.process(self.level_dbfs, t)
        if event and event["event"] == "start":
            self._voice_start_t = event["t"]
            self._partial_since_voice = False
        elif event and event["event"] == "end":
            self._voice_end_t = event["t"]

    def on_partial(self, t: float) -> None:
        if not self._partial_since_voice and self._voice_start_t is not None:
            self.first_partial_latency.add(max(0.0, (t - self._voice_start_t) * 1000))
            self._partial_since_voice = True

    def on_final(self, t: float) -> None:
        if self._voice_end_t is not None:
            self.final_latency.add(max(0.0, (t - self._voice_end_t) * 1000))

    def snapshot(self) -> dict:
        return {
            "level_dbfs": round(self.level_dbfs, 1),
            "silence_alert": self.silence.active,
            "voice_active": self.vad.in_voice,
            "last_frame_age_s": (
                round(time.monotonic() - self._last_frame_wall, 1) if self._last_frame_wall is not None else None
            ),
            "first_partial_latency_ms": {"p50": self.first_partial_latency.p50(),
                                          "p95": self.first_partial_latency.p95()},
            "final_latency_ms": {"p50": self.final_latency.p50(), "p95": self.final_latency.p95()},
        }


class DailyQuota:
    """Counts Live sessions opened today (Pacific time, like Google's RPD reset),
    persisted to DATA_DIR/quota.json so a restart doesn't lose the count."""

    def __init__(self, path: Path, now: "Callable[[], datetime] | None" = None):
        self.path = Path(path)
        self._now = now or (lambda: datetime.now(_PACIFIC))
        self._date, self._count = self._load()

    def _today(self) -> str:
        return self._now().date().isoformat()

    def _load(self) -> tuple[str, int]:
        today = self._today()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("date") == today:
                return today, int(data.get("count", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return today, 0

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"date": self._date, "count": self._count}), encoding="utf-8")
        except OSError as e:
            _log.error("quota.json write failed: %s", e)

    def increment(self) -> int:
        today = self._today()
        if today != self._date:
            self._date, self._count = today, 0
        self._count += 1
        self._save()
        return self._count

    def count_today(self) -> int:
        today = self._today()
        if today != self._date:
            return 0
        return self._count
