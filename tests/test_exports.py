from backend.post.exports import build_cues, median_latency_ms, to_md, to_srt, to_txt, to_vtt


def test_median_latency_ms_odd():
    events = [{"lat_ms": 100}, {"lat_ms": 300}, {"lat_ms": 200}]
    assert median_latency_ms(events) == 200


def test_median_latency_ms_ignores_missing():
    events = [{"lat_ms": None}, {"lat_ms": 100}]
    assert median_latency_ms(events) == 100


def test_median_latency_ms_empty():
    assert median_latency_ms([]) == 0.0


def test_build_cues_offsets_timestamps():
    events = [{"text": "hola", "t0": 2.0, "t1": 3.0, "lat_ms": 500}]
    cues = build_cues(events, offset_ms=500)
    assert cues[0].t0 == 1.5
    assert cues[0].t1 == 2.5


def test_build_cues_splits_long_final_proportionally():
    long_text = " ".join(["palabra"] * 30)  # bien por encima de 84 caracteres
    events = [{"text": long_text, "t0": 0.0, "t1": 10.0, "lat_ms": None}]
    cues = build_cues(events)
    assert len(cues) > 1
    total = sum(len(c.text.replace("\n", " ")) for c in cues)
    assert total <= len(long_text) + len(cues)  # tolerancia por espacios de wrap
    # los cues son contiguos y no se solapan
    for prev, nxt in zip(cues, cues[1:]):
        assert nxt.t0 >= prev.t1


def test_build_cues_respects_minimum_duration():
    events = [{"text": "hola", "t0": 0.0, "t1": 0.1, "lat_ms": None}]
    cues = build_cues(events)
    assert cues[0].t1 - cues[0].t0 >= 1.0


def test_to_srt_format():
    events = [{"text": "hola mundo", "t0": 62.5, "t1": 64.0, "lat_ms": None}]
    cues = build_cues(events)
    out = to_srt(cues)
    assert "1\n" in out
    assert "00:01:02,500 --> 00:01:04,000" in out
    assert "hola mundo" in out


def test_to_vtt_format():
    events = [{"text": "hola mundo", "t0": 62.5, "t1": 64.0, "lat_ms": None}]
    cues = build_cues(events)
    out = to_vtt(cues)
    assert out.startswith("WEBVTT\n")
    assert "00:01:02.500 --> 00:01:04.000" in out


def test_to_txt_joins_finals():
    events = [{"text": "uno", "t0": 0, "t1": 1}, {"text": "dos", "t0": 1, "t1": 2}]
    assert to_txt(events) == "uno\ndos\n"


def test_to_md_includes_metadata_and_marks():
    meta = {"title": "Charla X", "speaker": "Ana", "source_lang": "en", "target_lang": "es"}
    events_by_lang = {"es": [{"text": "hola", "t0": 65.0, "t1": 66.0}]}
    out = to_md(meta, events_by_lang)
    assert "# Charla X" in out
    assert "Ana" in out
    assert "[01:05] hola" in out
