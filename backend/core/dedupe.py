"""dedupe_overlap() — strip a repeated prefix from `new` after a fresh (non-resumed)
reconnect, using the tail of what was already emitted. Used only on the fallback path
of T2.1 (resumption handle rejected/expired); transparent resumption needs no dedupe."""

import re

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _norm_words(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def dedupe_overlap(prev_tail: str, new: str, max_words: int = 15) -> str:
    """Return `new` with its longest prefix that overlaps the last `max_words` of
    `prev_tail` removed (case/punctuation-insensitive match). If nothing overlaps,
    `new` is returned unchanged."""
    tail_words = _norm_words(prev_tail)[-max_words:]
    if not tail_words:
        return new

    new_tokens = list(_WORD_RE.finditer(new))
    if not new_tokens:
        return new
    new_words = [t.group(0).lower() for t in new_tokens]

    best_len = 0
    max_k = min(len(tail_words), len(new_words))
    for k in range(max_k, 0, -1):
        if tail_words[-k:] == new_words[:k]:
            best_len = k
            break
    if best_len == 0:
        return new

    cut_end = new_tokens[best_len - 1].end()
    remainder = new[cut_end:]
    return remainder.lstrip(" ,.;:!?…-")
