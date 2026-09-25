from datetime import datetime
from zoneinfo import ZoneInfo

from backend.core.metrics import DailyQuota, LatencyTracker, SilenceAlert, VoiceActivityDetector

PACIFIC = ZoneInfo("America/Los_Angeles")


def test_vad_ignores_a_short_dip_below_threshold_but_ends_after_the_hangover():
    vad = VoiceActivityDetector(threshold_dbfs=-40, hangover_s=0.3)
    assert vad.process(-10, t=0.0) == {"event": "start", "t": 0.0}
    assert vad.process(-60, t=0.1) is None  # short dip, still "in voice" (hangover)
    assert vad.in_voice
    assert vad.process(-10, t=0.15) is None  # back above threshold before the hangover elapsed
    assert vad.process(-60, t=0.2) is None  # still within the hangover window
    assert vad.process(-60, t=0.5) == {"event": "end", "t": 0.5}  # 0.35s since last above threshold
    assert not vad.in_voice


def test_silence_alert_fires_only_after_the_hold_time():
    alert = SilenceAlert(threshold_dbfs=-50, hold_s=20)
    assert alert.process(-70, t=0) is False
    assert alert.process(-70, t=19) is False
    assert alert.process(-70, t=20) is True
    assert alert.process(-10, t=21) is False  # loud again resets it
    assert alert.active is False


def test_latency_tracker_p50_p95():
    tracker = LatencyTracker()
    for ms in range(1, 101):  # 1..100
        tracker.add(ms)
    assert tracker.p50() == 51  # ~median of a 100-sample sorted list, nearest-rank
    assert tracker.p95() == 95


def test_latency_tracker_empty_is_none():
    assert LatencyTracker().p50() is None
    assert LatencyTracker().p95() is None


def test_quota_persists_across_instances_same_day(tmp_path):
    path = tmp_path / "quota.json"
    fixed_now = lambda: datetime(2026, 9, 24, 12, 0, tzinfo=PACIFIC)
    q1 = DailyQuota(path, now=fixed_now)
    assert q1.increment() == 1
    assert q1.increment() == 2
    q2 = DailyQuota(path, now=fixed_now)  # simulates a restart
    assert q2.count_today() == 2
    assert q2.increment() == 3


def test_quota_resets_on_a_new_pacific_day(tmp_path):
    path = tmp_path / "quota.json"
    day1 = DailyQuota(path, now=lambda: datetime(2026, 9, 24, 23, 0, tzinfo=PACIFIC))
    day1.increment()
    day1.increment()
    day2 = DailyQuota(path, now=lambda: datetime(2026, 9, 25, 1, 0, tzinfo=PACIFIC))
    assert day2.count_today() == 0
    assert day2.increment() == 1
