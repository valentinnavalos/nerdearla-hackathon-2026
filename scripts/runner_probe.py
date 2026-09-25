"""T2.10a at runner level: N Live rooms in one process with our own code, no FastAPI/WS.
Compare with scripts/live_probe.py (raw SDK) to locate where a degradation shows up.

Layers (docs/CONCURRENCY-REPORT.md, "Capas de prueba"):
  --layer engine   LiveTranslateEngine + FrameQueue + segmenter + glossary
  --layer session  the same through SessionManager: Session, CaptionWriter, fan-out to subscribers

    python -m scripts.runner_probe samples/en_talk_3min.mp3:en samples/es_talk_2min.mp3:es \\
        --seconds 60 --trials 3 --cooldown 300 --stagger 0 --label A2

Every trial is classified (scripts/probe_metrics.py) and the report, stamped with branch + commit
+ date + SDK (scripts/report_meta.py), is rewritten after each trial: DATA_DIR/probe/runner-*.json.
Exit code 3 = Gemini rejected a session for quota (429 / RESOURCE_EXHAUSTED): stop the sweep.
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from backend.config import DEFAULT_GLOSSARY_PATH, configure_logging, get_settings
from backend.core.glossary import Glossary
from backend.core.loop_monitor import LoopLagMonitor
from backend.core.manager import SessionManager
from backend.core.session import LANGS, other_lang
from backend.engine.base import SessionContext
from backend.engine.factory import create_engine
from backend.sources.base import FrameQueue, pump
from backend.sources.file_source import FileSource
from scripts.probe_metrics import baseline_from, classify, session_metrics
from scripts.report_meta import run_meta

QUOTA_MARKERS = ("429", "RESOURCE_EXHAUSTED", "quota")

log = logging.getLogger("probe")


class SlowCallbacks(logging.Handler):
    """Diagnostic only (asyncio debug mode, adds overhead): callbacks that held the loop >= slow_ms."""

    pattern = re.compile(r"Executing (.+) took ([\d.]+) seconds")

    def __init__(self):
        super().__init__()
        self.items: list[tuple[float, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        match = self.pattern.search(record.getMessage())
        if match:
            self.items.append((float(match.group(2)) * 1000, match.group(1)[:160]))

    def top(self, n: int = 5) -> list[dict]:
        return [{"ms": round(ms, 1), "what": what} for ms, what in sorted(self.items, reverse=True)[:n]]


def _settings(**update):
    return get_settings().model_copy(update={"engine": "live_translate", **update})


def _record(name, lang, path, delay, stats, finals, interims, dropped, elapsed, outcome, error, **extra) -> dict:
    stats = {**stats, "text_times": list(stats.get("text_times") or [])}
    record = {
        "name": name,
        "lang": lang,
        "file": path,
        "start_delay_s": delay,
        "elapsed_s": round(elapsed, 2),
        "outcome": outcome,
        "error": error,
        "stats": stats,
        "finals": dict(finals),
        "interims": interims,
        "interims_per_s": round(interims / elapsed, 2) if elapsed else 0.0,
        "dropped": dropped,
        **extra,
    }
    record["metrics"] = session_metrics(stats, elapsed, error)
    return record


async def engine_session(name: str, path: str, lang: str, delay: float, args, recorder) -> dict:
    """Layer `engine`: LiveTranslateEngine fed from a FrameQueue, cut after args.seconds."""
    await asyncio.sleep(delay)
    engine = create_engine(_settings())
    ctx = SessionContext(name, lang, other_lang(lang), Glossary.load(DEFAULT_GLOSSARY_PATH))
    queue = FrameQueue(maxsize=50)
    producer = asyncio.create_task(pump(FileSource(path), queue))
    finals: Counter = Counter()
    interims = 0

    async def emit(event) -> None:
        nonlocal interims
        if event.final:
            finals[event.kind] += 1
        else:
            interims += 1
        if recorder is not None:
            recorder(event.model_dump())

    t0 = time.monotonic()
    error = None
    try:
        await asyncio.wait_for(engine.run(queue, emit, ctx), timeout=args.seconds)
        outcome = "ended"
    except asyncio.TimeoutError:
        outcome = f"cut at {args.seconds:.0f}s"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        outcome = "error"
    finally:
        producer.cancel()
    elapsed = time.monotonic() - t0
    stats = engine.runner.stats if engine.runner else {}
    return _record(name, lang, path, delay, stats, finals, interims, queue.dropped_frames, elapsed, outcome,
                   error, callback_errors=engine.callback_errors)


async def session_layer(inputs: list[tuple[str, str, str, float]], args, recorder, data_dir: Path) -> list[dict]:
    """Layer `session`: the same rooms through SessionManager (Session + CaptionWriter + fan-out),
    each one with a subscriber per language. MAX_CONCURRENT_LIVE is raised to N for the probe."""
    settings = _settings(data_dir=data_dir, max_concurrent_live=len(inputs))
    built = []  # manager.start() builds the engine synchronously: built[-1] is that room's engine
    manager = SessionManager(settings, engine_factory=lambda: built.append(create_engine(settings)) or built[-1])

    async def consume(queue: asyncio.Queue, counts: Counter) -> None:
        while True:
            msg = await queue.get()
            if msg.get("type") != "caption":
                continue
            counts["final" if msg["final"] else "interim", msg["kind"]] += 1
            if recorder is not None:
                recorder(msg)

    async def one(name: str, path: str, lang: str, delay: float) -> dict:
        await asyncio.sleep(delay)
        room = manager.create(name, source_lang=lang, source="file", file=path)
        counts: Counter = Counter()
        consumers = [asyncio.create_task(consume(manager.subscribe(room.id, l), counts)) for l in LANGS]
        t0 = time.monotonic()
        manager.start(room.id)
        engine = built[-1]
        try:
            await asyncio.wait_for(asyncio.shield(room._task), timeout=args.seconds)
            outcome = "ended"
        except asyncio.TimeoutError:
            outcome = f"cut at {args.seconds:.0f}s"
        elapsed = time.monotonic() - t0
        await manager.stop(room.id)  # drains the CaptionWriter too
        for task in consumers:
            task.cancel()
        finals = Counter({kind: counts["final", kind] for kind in ("orig", "trans")})
        interims = counts["interim", "orig"] + counts["interim", "trans"]
        if room.last_error:
            outcome = "error"
        info = room.info()["metrics"]
        return _record(name, lang, path, delay, engine.runner.stats if engine.runner else {}, finals, interims,
                       room.dropped_frames, elapsed, outcome, room.last_error,
                       callback_errors=engine.callback_errors, room_status=room.status.value,
                       captions_written=info["captions_written"], write_errors=info["write_errors"],
                       append_ms_max=info["append_ms_max"])

    try:
        return await asyncio.gather(*(one(n, p, l, d) for n, p, l, d in inputs))
    finally:
        await manager.stop_all()


async def run_trial(trial: int, inputs: list[tuple[str, str, str]], args, recorder) -> dict:
    loop = asyncio.get_running_loop()
    slow = None
    if args.slow_ms:
        loop.set_debug(True)
        loop.slow_callback_duration = args.slow_ms / 1000
        slow = SlowCallbacks()
        logging.getLogger("asyncio").addHandler(slow)
    monitor = LoopLagMonitor()
    monitor.start()
    started = time.time()
    try:
        timed = [(n, p, l, i * args.stagger) for i, (n, p, l) in enumerate(inputs)]
        if args.layer == "engine":
            sessions = await asyncio.gather(*(engine_session(n, p, l, d, args, recorder) for n, p, l, d in timed))
        else:
            with tempfile.TemporaryDirectory(prefix="probe-") as tmp:
                sessions = await session_layer(timed, args, recorder, Path(tmp))
    finally:
        await monitor.stop()
        if slow is not None:
            logging.getLogger("asyncio").removeHandler(slow)
            loop.set_debug(False)
    return {
        "trial": trial,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(started)),
        "loop_lag": monitor.stats(),
        "slow_callbacks": slow.top() if slow else None,
        "sessions": list(sessions),
    }


def print_trial(trial: dict, baseline: dict | None) -> None:
    lag = trial["loop_lag"]
    print(f"\n--- trial {trial['trial']} ({trial['started_at']})  loop lag p99={lag['lag_ms_p99']} ms "
          f"max={lag['lag_ms_max']} ms")
    print(f"{'session':8} {'lang':4} {'class':19} {'connect':>7} {'1st_txt':>7} {'txt/s':>6} {'gap95':>6} "
          f"{'gapmax':>6} {'stall':>6} {'fin o/t':>8} {'drop':>5} {'disp_ms':>7}  outcome")
    for s in trial["sessions"]:
        cls, reasons = classify(s, baseline)
        st, m = s["stats"], s["metrics"]

        def f(v, fmt="{:.1f}"):
            return fmt.format(v) if v is not None else "-"

        print(f"{s['name']:8} {s['lang']:4} {cls:19} {f(st.get('connect_ms'), '{}'):>7} "
              f"{f(st.get('first_text_s')):>7} {m['text_msgs_per_s']:>6.2f} {f(m['gap_p95_s']):>6} "
              f"{f(m['time_without_messages_max_s']):>6} {f(m['stall_max_s']):>6} "
              f"{s['finals'].get('orig', 0):>3}/{s['finals'].get('trans', 0):<4} {s['dropped']:>5} "
              f"{st.get('dispatch_ms_max', 0):>7.1f}  {s['outcome']} {s['error'] or ''} {'; '.join(reasons)}")
    if trial["slow_callbacks"]:
        print("slow callbacks:", trial["slow_callbacks"])


async def main_async(args) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    inputs = []
    for i, item in enumerate(args.inputs):
        path, _, lang = item.rpartition(":")
        if lang not in LANGS or not Path(path).exists():
            raise SystemExit(f"bad input {item!r}: expected an existing audio_file:lang (lang = en | es)")
        inputs.append((chr(ord("A") + i), path, lang))

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = Path(args.out or Path(settings.data_dir) / "probe" / f"runner-{args.label or 'run'}-{stamp}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    events = {"file": None}  # one file per trial: <report>.t<N>.events.jsonl
    recorder = None
    if args.record_events:

        def recorder(msg: dict) -> None:
            events["file"].write(json.dumps(msg, ensure_ascii=False) + "\n")

    baseline = None
    if args.baseline:
        report = json.loads(Path(args.baseline).read_text())
        baseline = baseline_from([s for t in report["trials"] for s in t["sessions"]])

    report = {
        "meta": run_meta(args, label=args.label, model=settings.live_translate_model, layer=args.layer,
                         sessions=len(inputs), record_events=args.record_events),
        "trials": [],
    }
    exit_code = 0
    for trial in range(1, args.trials + 1):
        if trial > 1 and args.cooldown:
            log.info("cooldown %.0f s before trial %d", args.cooldown, trial)
            await asyncio.sleep(args.cooldown)
        if args.record_events:
            events["file"] = out.with_suffix(f".t{trial}.events.jsonl").open("w", encoding="utf-8")
        try:
            result = await run_trial(trial, inputs, args, recorder)
        finally:
            if events["file"] is not None:
                events["file"].close()
        report["trials"].append(result)
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
        print_trial(result, baseline)
        errors = [s["error"] for s in result["sessions"] if s["error"]]
        if any(marker.lower() in e.lower() for e in errors for marker in QUOTA_MARKERS):
            log.error("quota rejection, stopping: %s", errors)
            exit_code = 3
            break
    print(f"\nreport: {out}")
    return exit_code


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="T2.10a: N Live rooms in one process, classified and reported")
    p.add_argument("inputs", nargs="+", help="audio_file:lang (lang = en | es); one session per input")
    p.add_argument("--seconds", type=float, default=60, help="cut every session after N seconds")
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--cooldown", type=float, default=300, help="seconds without Live usage between trials")
    p.add_argument("--stagger", type=float, default=0, help="seconds between session starts")
    p.add_argument("--layer", choices=("engine", "session"), default="engine")
    p.add_argument("--label", default="", help="block name in the sweep (A1, A2...)")
    p.add_argument("--baseline", help="report of the baseline block, to classify against it")
    p.add_argument("--slow-ms", type=float, default=0,
                   help="diagnostic: asyncio debug mode, log callbacks slower than this (adds overhead)")
    p.add_argument("--record-events", action="store_true",
                   help="write every interim + final to <report>.t<N>.events.jsonl (REPLAY_FILE for audience_load)")
    p.add_argument("--out", help="report path (default DATA_DIR/probe/runner-<label>-<ts>.json)")
    sys.exit(asyncio.run(main_async(p.parse_args())))


if __name__ == "__main__":
    main()
