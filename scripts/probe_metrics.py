"""Derived metrics + objective classification for the concurrency probes (runner_probe).

The thresholds are fixed here, before looking at the sweep results, and copied into
docs/CONCURRENCY-REPORT.md. msgs/s alone hides the failure seen in T1.4/T2.10a (a session
that stalls for tens of seconds and then bursts), so the gaps between text messages count too.

Re-classify saved reports against a baseline (the A1 block of the same sweep):

    python -m scripts.probe_metrics data/probe/runner-*.json --baseline data/probe/runner-A1.json
"""

import argparse
import json
import statistics
from pathlib import Path

# --- thresholds (see CONCURRENCY-REPORT.md, "Clasificación") ---------------------------------
SILENT_GAP_S = 10.0  # this long without text AFTER the first one = the captions froze (a slow start is DEGRADED)
FIRST_TEXT_FACTOR, FIRST_TEXT_MARGIN_S = 2.0, 3.0  # degraded when > 2x baseline AND > baseline + 3 s
GAP_P95_FACTOR, GAP_P95_MARGIN_S = 2.0, 1.0  # degraded when > 2x baseline AND > baseline + 1 s
TEXT_RATE_FACTOR = 0.5  # degraded when below half the baseline text messages/s
REJECTION_MARKERS = ("429", "RESOURCE_EXHAUSTED", "quota", "1008", "1011", "PERMISSION_DENIED", "UNAVAILABLE")

CLASSES = ("ACCEPTED", "REJECTED_EXPLICITLY", "DEGRADED", "SILENT_DEGRADATION", "NO_RESPONSE", "TIMEOUT")


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def text_gaps(text_times: list[float], end_s: float | None) -> list[float]:
    """Stretches without text, in seconds after connecting: connect -> 1st text, between texts,
    last text -> end of the measured window. No text at all = one gap as long as the window."""
    points = [0.0, *sorted(text_times)]
    if end_s is not None and end_s > points[-1]:
        points.append(end_s)
    return [round(b - a, 3) for a, b in zip(points, points[1:])]


def is_rejection(error: str | None) -> bool:
    return bool(error) and any(marker.lower() in error.lower() for marker in REJECTION_MARKERS)


def session_metrics(stats: dict, elapsed_s: float, error: str | None) -> dict:
    """Metrics derived from runner.stats for one session measured for `elapsed_s` wall seconds."""
    connected = stats.get("connect_ms") is not None
    times = list(stats.get("text_times") or [])
    end_s = None
    if connected:
        end_s = elapsed_s - stats["connect_ms"] / 1000
        if error and stats.get("first_error_s") is not None:
            end_s = min(end_s, stats["first_error_s"])
    gaps = text_gaps(times, end_s) if connected else []
    after_first = gaps[1:] if times else []  # connect -> 1st text is first_text_s, kept out of the percentiles
    active_s = end_s if end_s else 0.0
    return {
        "connected": connected,
        "text_msgs": len(times),
        "text_msgs_per_s": round(len(times) / active_s, 2) if active_s > 0 else 0.0,
        "gap_p50_s": percentile(after_first, 0.50),
        "gap_p95_s": percentile(after_first, 0.95),
        "gap_p99_s": percentile(after_first, 0.99),
        "time_without_messages_max_s": max(gaps, default=None),
        "stall_max_s": max(after_first, default=None),
        "last_success_s": stats.get("last_text_s"),
        "first_error_s": stats.get("first_error_s"),
        "effective_s": round(active_s, 1),
    }


def baseline_from(sessions: list[dict]) -> dict | None:
    """Median first_text / gap p95 / text rate over the sessions of the baseline block."""
    ok = [s for s in sessions if s["metrics"]["text_msgs"] > 0]
    if not ok:
        return None

    def median(key: str, source: str = "metrics") -> float:
        values = [s[source][key] for s in ok if s[source].get(key) is not None]
        return statistics.median(values) if values else 0.0

    return {
        "first_text_s": median("first_text_s", "stats"),
        "gap_p95_s": median("gap_p95_s"),
        "text_msgs_per_s": median("text_msgs_per_s"),
        "sessions": len(ok),
    }


def classify(session: dict, baseline: dict | None = None) -> tuple[str, list[str]]:
    """(class, reasons) for one session record (as written by runner_probe)."""
    m, st, error = session["metrics"], session["stats"], session.get("error")
    if not m["connected"]:
        if error:
            return "REJECTED_EXPLICITLY", [f"no conectó: {error}"]
        return "TIMEOUT", ["no conectó dentro de la ventana"]
    if m["text_msgs"] == 0:
        if is_rejection(error):
            return "REJECTED_EXPLICITLY", [f"conectó y el servidor cortó sin texto: {error}"]
        return "NO_RESPONSE", ["conectó, 0 mensajes con texto"]
    if is_rejection(error):
        return "REJECTED_EXPLICITLY", [f"el servidor cortó a los {m['first_error_s']} s: {error}"]
    reasons = []
    stall = m["stall_max_s"] or 0.0
    if stall >= SILENT_GAP_S:
        return "SILENT_DEGRADATION", [f"{stall:.1f} s sin texto después del primero (umbral {SILENT_GAP_S:.0f} s)"]
    if error:
        reasons.append(f"error: {error}")
    if baseline:
        ft, base_ft = st.get("first_text_s"), baseline["first_text_s"]
        if ft is not None and ft > base_ft * FIRST_TEXT_FACTOR and ft > base_ft + FIRST_TEXT_MARGIN_S:
            reasons.append(f"first_text {ft:.1f} s vs base {base_ft:.1f} s")
        p95, base_p95 = m["gap_p95_s"] or 0.0, baseline["gap_p95_s"]
        if p95 > base_p95 * GAP_P95_FACTOR and p95 > base_p95 + GAP_P95_MARGIN_S:
            reasons.append(f"gap p95 {p95:.1f} s vs base {base_p95:.1f} s")
        rate, base_rate = m["text_msgs_per_s"], baseline["text_msgs_per_s"]
        if base_rate and rate < base_rate * TEXT_RATE_FACTOR:
            reasons.append(f"{rate:.2f} textos/s vs base {base_rate:.2f}")
    return ("DEGRADED", reasons) if reasons else ("ACCEPTED", [])


# --- summary of saved reports ----------------------------------------------------------------

def load_sessions(report: dict) -> list[dict]:
    return [s for trial in report["trials"] for s in trial["sessions"]]


def summarize(paths: list[str], baseline_path: str | None) -> str:
    baseline = None
    if baseline_path:
        baseline = baseline_from(load_sessions(json.loads(Path(baseline_path).read_text())))
    out = []
    if baseline:
        out.append(f"Baseline ({baseline_path}, {baseline['sessions']} sesiones): first_text "
                   f"{baseline['first_text_s']:.1f} s · gap p95 {baseline['gap_p95_s']:.1f} s · "
                   f"{baseline['text_msgs_per_s']:.2f} textos/s\n")
    out.append("| reporte | trial | sesión | clase | connect_ms | 1er texto | textos/s | gap p95 | gap máx | stall "
               "| fin orig/trans | interims/s | dropped | dispatch máx | lag p99/máx | motivo |")
    out.append("|" + "---|" * 16)
    for path in paths:
        report = json.loads(Path(path).read_text())
        label = report["meta"].get("label") or Path(path).stem
        for trial in report["trials"]:
            lag = trial.get("loop_lag") or {}
            for s in trial["sessions"]:
                cls, reasons = classify(s, baseline)
                m, st = s["metrics"], s["stats"]
                ft = f"{st['first_text_s']:.1f}" if st.get("first_text_s") is not None else "-"
                p95 = f"{m['gap_p95_s']:.1f}" if m["gap_p95_s"] is not None else "-"
                gmax = f"{m['time_without_messages_max_s']:.1f}" if m["time_without_messages_max_s"] is not None else "-"
                stall = f"{m['stall_max_s']:.1f}" if m["stall_max_s"] is not None else "-"
                out.append(
                    f"| {label} | {trial['trial']} | {s['name']} ({s['lang']}) | **{cls}** | "
                    f"{st.get('connect_ms') or '-'} | {ft} | {m['text_msgs_per_s']:.2f} | {p95} | {gmax} | {stall} | "
                    f"{s['finals'].get('orig', 0)}/{s['finals'].get('trans', 0)} | {s['interims_per_s']:.2f} | "
                    f"{s['dropped']} | {st.get('dispatch_ms_max', 0):.1f} | "
                    f"{lag.get('lag_ms_p99', '-')}/{lag.get('lag_ms_max', '-')} | {'; '.join(reasons)} |"
                )
    return "\n".join(out)


def main() -> None:
    p = argparse.ArgumentParser(description="Re-classify runner_probe reports as a markdown table")
    p.add_argument("reports", nargs="+")
    p.add_argument("--baseline", help="report of the baseline block (N=1)")
    args = p.parse_args()
    print(summarize(args.reports, args.baseline))


if __name__ == "__main__":
    main()
