"""Transcription fragments -> interim/final captions (Camino 1). One Segmenter per track.

Pure (time is passed in) so the rules are unit-testable. A final closes the current
`seg` and opens the next one when:
  - a sentence terminator (. ? ! …) closes at least `min_final_chars` characters;
  - the text grows past `max_chars` (cut at the last space);
  - no fragment arrives for `idle_s` (driven by tick()).
"""

import re
from dataclasses import dataclass

_SPACES = re.compile(r"\s+")
# terminator (plus closing quotes/brackets) followed by whitespace or the end of the text
_SENTENCE_END = re.compile(r"[.?!…]+[\"'”’)\]]*(?=\s|$)")


@dataclass
class Piece:
    seg: int
    text: str
    final: bool
    t0: float
    t1: float


class Segmenter:
    def __init__(self, min_final_chars: int = 20, max_chars: int = 120, idle_s: float = 2.0):
        self.min_final_chars = min_final_chars
        self.max_chars = max_chars
        self.idle_s = idle_s
        self.seg = 1
        self._buf = ""  # committed text of the open segment (single-spaced, may end in a space)
        self._t0: float | None = None
        self._last = 0.0

    def feed(self, fragment: str, now: float) -> list[Piece]:
        """Append a delta fragment (fragments are concatenated as received)."""
        if not fragment:
            return []
        if self._t0 is None:
            self._t0 = now
        self._last = now
        self._buf = _SPACES.sub(" ", self._buf + fragment).lstrip()
        out = self._cut(now)
        if self._buf.strip():
            out.append(Piece(self.seg, self._buf.strip(), False, self._t0, now))
        return out

    def preview(self, hypothesis: str, now: float) -> list[Piece]:
        """Interim for a not-yet-committed hypothesis: shown after the committed text, not stored."""
        if not hypothesis.strip():
            return []
        if self._t0 is None:
            self._t0 = now
        text = _SPACES.sub(" ", f"{self._buf} {hypothesis}").strip()
        return [Piece(self.seg, text, False, self._t0, now)]

    def tick(self, now: float) -> list[Piece]:
        if self._buf.strip() and now - self._last >= self.idle_s:
            return self.flush(now)
        return []

    def flush(self, now: float) -> list[Piece]:
        if not self._buf.strip():
            return []
        piece = self._final(self._buf, now)
        self._buf, self._t0 = "", None
        return [piece]

    def _cut(self, now: float) -> list[Piece]:
        out = []
        while True:
            end = next(
                (m.end() for m in _SENTENCE_END.finditer(self._buf) if m.end() >= self.min_final_chars),
                None,
            )
            if end is None and len(self._buf.strip()) > self.max_chars:
                end = self._buf.rfind(" ", 0, self.max_chars + 1)
                if end <= 0:
                    end = self.max_chars
            if end is None:
                return out
            out.append(self._final(self._buf[:end], now))
            self._buf = self._buf[end:].lstrip()
            self._t0 = now if self._buf else None

    def _final(self, text: str, now: float) -> Piece:
        piece = Piece(self.seg, text.strip(), True, self._t0 if self._t0 is not None else now, now)
        self.seg += 1
        return piece
