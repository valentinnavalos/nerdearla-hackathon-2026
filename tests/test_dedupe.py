from backend.core.dedupe import dedupe_overlap


def test_removes_repeated_prefix():
    assert dedupe_overlap("hello there world", "world how are you") == "how are you"


def test_case_and_punctuation_insensitive():
    assert dedupe_overlap("we talked about Kubernetes.", "kubernetes and terraform") == "and terraform"


def test_no_overlap_returns_new_unchanged():
    assert dedupe_overlap("hello there", "completely different text") == "completely different text"


def test_empty_prev_tail_returns_new_unchanged():
    assert dedupe_overlap("", "some new text") == "some new text"


def test_full_overlap_returns_empty():
    assert dedupe_overlap("the quick brown fox", "the quick brown fox") == ""
