from scripts.probe_metrics import baseline_from, classify, session_metrics, text_gaps


def _session(text_times, connect_ms=300, elapsed=60.0, error=None, first_text=None, first_error_s=None):
    stats = {
        "connect_ms": connect_ms,
        "text_times": text_times,
        "first_text_s": first_text if first_text is not None else (text_times[0] if text_times else None),
        "last_text_s": text_times[-1] if text_times else None,
        "first_error_s": first_error_s,
    }
    return {"stats": stats, "error": error, "metrics": session_metrics(stats, elapsed, error)}


def test_gaps_include_the_start_and_the_end_of_the_window():
    assert text_gaps([2.0, 3.0, 7.0], 10.0) == [2.0, 1.0, 4.0, 3.0]
    assert text_gaps([], 10.0) == [10.0]


def test_a_long_stall_is_silent_degradation_even_with_a_normal_rate():
    # ~2 texts/s like a healthy session, but frozen for 18 s in the middle
    times = [4 + i * 0.5 for i in range(40)] + [42 + i * 0.5 for i in range(35)]
    s = _session(times)
    assert s["metrics"]["time_without_messages_max_s"] >= 18
    cls, reasons = classify(s)
    assert cls == "SILENT_DEGRADATION" and "18" in reasons[0]


def test_classes_for_no_text_rejection_and_timeout():
    assert classify(_session([]))[0] == "NO_RESPONSE"
    assert classify(_session([], error="APIError: 429 RESOURCE_EXHAUSTED"))[0] == "REJECTED_EXPLICITLY"
    assert classify(_session([], connect_ms=None, error="ConnectionClosedError: 1008"))[0] == "REJECTED_EXPLICITLY"
    assert classify(_session([], connect_ms=None))[0] == "TIMEOUT"


def test_degraded_against_the_baseline():
    healthy = [4 + i * 0.5 for i in range(110)]
    baseline = baseline_from([_session(healthy), _session(healthy)])
    assert classify(_session(healthy), baseline) == ("ACCEPTED", [])
    slow_start = [13 + i * 0.5 for i in range(90)]  # first text at 13 s instead of 4 s
    cls, reasons = classify(_session(slow_start), baseline)
    assert cls == "DEGRADED" and "first_text" in reasons[0]
    sparse = [4 + i * 3 for i in range(19)]  # every 3 s: gaps below 10 s but far from baseline
    cls, reasons = classify(_session(sparse), baseline)
    assert cls == "DEGRADED" and any("gap p95" in r for r in reasons)
