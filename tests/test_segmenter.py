from backend.core.segmenter import Segmenter


def test_each_fragment_emits_accumulated_interim():
    s = Segmenter()
    assert [(p.text, p.final) for p in s.feed("Hello", 0.0)] == [("Hello", False)]
    assert [(p.text, p.final) for p in s.feed(" everyone", 0.3)] == [("Hello everyone", False)]


def test_terminator_closes_segment_and_opens_next():
    s = Segmenter()
    s.feed("Welcome to Nerdearla", 0.0)
    out = s.feed(" everyone.", 0.5)
    assert [(p.seg, p.text, p.final, p.t0, p.t1) for p in out] == [
        (1, "Welcome to Nerdearla everyone.", True, 0.0, 0.5)
    ]
    assert s.feed(" Today", 0.8)[0].seg == 2


def test_short_sentence_waits_for_more_text():
    s = Segmenter()
    assert [p.final for p in s.feed("Hi.", 0.0)] == [False]
    out = s.feed(" Today we talk about Kubernetes.", 0.5)
    assert [(p.text, p.final) for p in out] == [("Hi. Today we talk about Kubernetes.", True)]


def test_terminator_in_the_middle_of_a_fragment():
    s = Segmenter()
    out = s.feed("Thanks for coming to this talk. So let's", 1.0)
    assert [(p.seg, p.text, p.final) for p in out] == [
        (1, "Thanks for coming to this talk.", True),
        (2, "So let's", False),
    ]


def test_long_text_is_cut_at_last_space():
    s = Segmenter(max_chars=30)
    out = s.feed("one two three four five six seven eight nine", 0.0)
    finals = [p for p in out if p.final]
    assert finals[0].text == "one two three four five six"
    assert out[-1].text == "seven eight nine" and not out[-1].final


def test_idle_finalizes_and_flush_drains():
    s = Segmenter(idle_s=1.2)
    s.feed("no punctuation here", 0.0)
    assert s.tick(1.0) == []
    assert [(p.text, p.final) for p in s.tick(1.3)] == [("no punctuation here", True)]
    assert s.tick(5.0) == []
    s.feed("tail", 6.0)
    assert [(p.seg, p.final) for p in s.flush(6.1)] == [(2, True)]


def test_preview_shows_hypothesis_without_committing():
    s = Segmenter()
    s.feed("Hello", 0.0)
    assert s.preview("wor", 0.2)[0].text == "Hello wor"
    assert s.feed(" world", 0.4)[-1].text == "Hello world"


def test_idle_cutoff_is_configurable():
    s = Segmenter(idle_s=2.0)
    s.feed("half a sentence", 0.0)
    assert s.tick(1.5) == []  # a normal gap between fragments no longer cuts the phrase
    assert [p.final for p in s.tick(2.0)] == [True]
