import asyncio
import time

from backend.core.loop_monitor import LoopLagMonitor


def test_idle_loop_has_low_lag_and_a_blocking_call_shows_up():
    async def main():
        monitor = LoopLagMonitor(interval=0.02)
        monitor.start()
        await asyncio.sleep(0.3)
        idle = monitor.stats()
        time.sleep(0.3)  # blocks the whole loop, like a sync disk write would
        await asyncio.sleep(0.1)
        await monitor.stop()
        return idle, monitor.stats()

    idle, after = asyncio.run(main())
    assert idle["samples"] > 5 and idle["lag_ms_max"] < 50
    assert after["lag_ms_max"] >= 250 and after["over_100ms"] >= 1


def test_window_and_reset():
    monitor = LoopLagMonitor()
    now = time.monotonic()
    monitor.record(now - 60, 500.0)  # old spike, outside a 10 s window
    monitor.record(now, 5.0)
    assert monitor.stats(window_s=10)["lag_ms_max"] == 5.0
    assert monitor.stats()["lag_ms_max"] == 500.0
    monitor.reset()
    assert monitor.stats()["samples"] == 0 and monitor.lag_ms_max == 0
