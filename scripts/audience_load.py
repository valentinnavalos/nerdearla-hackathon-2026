"""Audience scaling without Gemini: K caption clients against a running server in replay mode.
Measures our fan-out (SessionManager -> queues -> WS), independently of the Live quota.

    ENGINE=replay DEMO_ROOMS=2 REPLAY_FILE=<events.jsonl> uvicorn backend.app:app --port 7860
    python -m scripts.audience_load --clients 10,50,100,200 --seconds 60 --server-pid <uvicorn pid>

Per level: connections ok/failed, messages per client and missing ones (a slow client loses its
oldest messages by design), fan-out spread (the same caption reaching every client of its room and
language: max - min arrival), server loop lag (/healthz), server CPU % and RSS (/proc/<pid>, needs
the same PID namespace: run it with `docker exec` in the server container), and the lag of this
process's own loop: if that one is high, the load generator is the bottleneck, not the server.
Report: DATA_DIR/probe/audience-<ts>.json, stamped with branch + commit + date.
"""

import argparse
import asyncio
import json
import os
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

import websockets

from backend.core.loop_monitor import LoopLagMonitor
from scripts.probe_metrics import percentile
from scripts.report_meta import run_meta

WARMUP_S = 2.0  # after every client connected: skip the history each one gets on connect
CLK_TCK = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100


def get_json(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


class ProcSampler:
    """CPU % and RSS of a local process from /proc (no psutil in the image)."""

    def __init__(self, pid: int | None):
        self.pid = pid
        self._last: tuple[float, float] | None = None

    def _cpu_s(self) -> float:
        fields = Path(f"/proc/{self.pid}/stat").read_text().rsplit(")", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / CLK_TCK  # utime + stime

    def sample(self) -> dict | None:
        if not self.pid:
            return None
        try:
            now, cpu = time.monotonic(), self._cpu_s()
            rss_kb = next(int(line.split()[1]) for line in Path(f"/proc/{self.pid}/status").read_text().splitlines()
                          if line.startswith("VmRSS:"))
        except (OSError, StopIteration, IndexError):
            return None
        pct = None
        if self._last is not None:
            pct = round(100 * (cpu - self._last[1]) / max(1e-6, now - self._last[0]), 1)
        self._last = (now, cpu)
        return {"cpu_pct": pct, "rss_mb": round(rss_kb / 1024, 1)}


async def client(ws_url: str, room: str, lang: str, deadline_box: dict, measure_from: dict, arrivals, stats):
    try:
        async with websockets.connect(f"{ws_url}/ws/captions/{room}?lang={lang}", open_timeout=10,
                                      max_queue=None) as ws:
            stats["connected"] += 1
            received = 0
            while True:
                remaining = deadline_box["t"] - time.monotonic()
                if remaining <= 0:
                    break
                try:  # re-check the deadline at least every second (it is set once all connected)
                    raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, 1.0))
                except asyncio.TimeoutError:
                    continue
                now = time.monotonic()
                msg = json.loads(raw)
                if msg.get("type") != "caption" or now < measure_from["t"]:
                    continue
                received += 1
                key = (room, lang, msg["seg"], msg["final"], msg["text"])
                arrivals[key].append(now)
            stats["received"].append(((room, lang), received))
    except Exception as e:
        stats["failed"] += 1
        stats["errors"].append(f"{type(e).__name__}: {e}"[:120])


async def run_level(n_clients: int, args, rooms: list[str]) -> dict:
    ws_url = args.url.replace("http", "ws", 1)
    targets = [(room, lang) for room in rooms for lang in ("en", "es")]
    arrivals: dict[tuple, list[float]] = defaultdict(list)
    stats = {"connected": 0, "failed": 0, "received": [], "errors": []}
    far = time.monotonic() + 3600
    deadline_box, measure_from = {"t": far}, {"t": far}
    own_lag = LoopLagMonitor()
    own_lag.start()
    tasks = [asyncio.create_task(client(ws_url, *targets[i % len(targets)], deadline_box, measure_from, arrivals, stats))
             for i in range(n_clients)]
    t_connect = time.monotonic()
    while stats["connected"] + stats["failed"] < n_clients and time.monotonic() - t_connect < 30:
        await asyncio.sleep(0.05)
    connect_s = time.monotonic() - t_connect
    measure_from["t"] = time.monotonic() + WARMUP_S
    deadline_box["t"] = measure_from["t"] + args.seconds
    own_lag.reset()

    sampler = ProcSampler(args.server_pid)
    sampler.sample()
    server = {"lag_ms_p99_max": 0.0, "lag_ms_max": 0.0, "cpu_pct": [], "rss_mb": []}
    while time.monotonic() < deadline_box["t"]:
        await asyncio.sleep(1)
        try:
            lag = (await asyncio.to_thread(get_json, f"{args.url}/healthz")).get("loop_lag_ms") or {}
            server["lag_ms_p99_max"] = max(server["lag_ms_p99_max"], lag.get("lag_ms_p99", 0))
            server["lag_ms_max"] = max(server["lag_ms_max"], lag.get("lag_ms_max", 0))
        except Exception:
            pass
        proc = sampler.sample()
        if proc and proc["cpu_pct"] is not None and time.monotonic() >= measure_from["t"]:
            server["cpu_pct"].append(proc["cpu_pct"])
            server["rss_mb"].append(proc["rss_mb"])
    await asyncio.gather(*tasks)
    await own_lag.stop()

    # expected per (room, lang) = every caption any client of that stream got in the window
    expected = defaultdict(set)
    for key in arrivals:
        expected[key[:2]].add(key)
    missing = [len(expected[stream]) - got for stream, got in stats["received"]]
    per_client = [got for _, got in stats["received"]]
    spreads = [(max(ts) - min(ts)) * 1000 for ts in arrivals.values() if len(ts) > 1]
    return {
        "clients": n_clients,
        "rooms": len(rooms),
        "connected": stats["connected"],
        "failed": stats["failed"],
        "errors": sorted(set(stats["errors"]))[:5],
        "connect_all_s": round(connect_s, 2),
        "msgs_per_client": {"min": min(per_client, default=0), "p50": percentile(per_client, 0.5),
                            "max": max(per_client, default=0)},
        "missing_per_client": {"max": max(missing, default=0), "clients_with_missing": sum(m > 0 for m in missing)},
        "fanout_spread_ms": {"p50": round(percentile(spreads, 0.5) or 0, 1),
                             "p99": round(percentile(spreads, 0.99) or 0, 1),
                             "max": round(max(spreads, default=0), 1)},
        "server_loop_lag_ms": {"p99_max": server["lag_ms_p99_max"], "max": server["lag_ms_max"]},
        "server_cpu_pct": {"avg": round(sum(server["cpu_pct"]) / len(server["cpu_pct"]), 1) if server["cpu_pct"] else None,
                           "max": max(server["cpu_pct"], default=None)},
        "server_rss_mb_max": max(server["rss_mb"], default=None),
        "client_loop_lag_ms": own_lag.stats(),
    }


def print_level(r: dict) -> None:
    cpu = r["server_cpu_pct"]
    print(f"{r['clients']:>7} {r['connected']:>5}/{r['failed']:<3} {r['msgs_per_client']['p50'] or 0:>8} "
          f"{r['missing_per_client']['max']:>7} {r['fanout_spread_ms']['p50']:>8} {r['fanout_spread_ms']['p99']:>8} "
          f"{r['fanout_spread_ms']['max']:>8} {r['server_loop_lag_ms']['p99_max']:>9} {r['server_loop_lag_ms']['max']:>8} "
          f"{cpu['avg'] if cpu['avg'] is not None else '-':>7} {r['server_rss_mb_max'] or '-':>7} "
          f"{r['client_loop_lag_ms']['lag_ms_p99']:>9}")


async def main_async(args) -> None:
    rooms = args.rooms.split(",") if args.rooms else [s["id"] for s in get_json(f"{args.url}/api/public/sessions")]
    if not rooms:
        raise SystemExit("the server has no rooms: start it with ENGINE=replay (DEMO_ROOMS=N)")
    report = {"meta": run_meta(args, rooms=rooms, label=args.label), "levels": []}
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    out = Path(args.out or data_dir / "probe" / f"audience-{args.label or 'run'}-{time.strftime('%Y%m%d-%H%M%S')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    print(f"rooms={rooms}  {args.seconds:.0f} s per level")
    print(f"{'clients':>7} {'ok/fail':>9} {'msgs_p50':>8} {'miss_max':>7} {'sprd_p50':>8} {'sprd_p99':>8} "
          f"{'sprd_max':>8} {'srv_lag99':>9} {'srv_lag':>8} {'cpu_avg':>7} {'rss_mb':>7} {'cli_lag99':>9}")
    for i, n in enumerate(int(x) for x in args.clients.split(",")):
        if i:
            await asyncio.sleep(args.pause)
        result = await run_level(n, args, rooms)
        report["levels"].append(result)
        out.write_text(json.dumps(report, indent=1, default=str))
        print_level(result)
    print(f"\nreport: {out}")


def main() -> None:
    p = argparse.ArgumentParser(description="Audience fan-out load test (replay rooms, no Gemini)")
    p.add_argument("--url", default="http://localhost:7860")
    p.add_argument("--clients", default="10,50,100,200", help="comma-separated levels")
    p.add_argument("--seconds", type=float, default=60, help="measured seconds per level")
    p.add_argument("--rooms", default="", help="comma-separated room ids (default: every public room)")
    p.add_argument("--server-pid", type=int, default=None, help="uvicorn pid, for CPU/RSS via /proc")
    p.add_argument("--pause", type=float, default=3, help="seconds between levels")
    p.add_argument("--label", default="")
    p.add_argument("--out")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
