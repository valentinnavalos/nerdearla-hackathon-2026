import json
import re
from pathlib import Path


class Glossary:
    """Loads terms/replacements and normalizes text against them."""

    def __init__(self, terms: list[str] | None = None, replacements: dict[str, str] | None = None):
        self.terms = terms or []
        self.replacements = replacements or {}
        self._replacement_patterns = [
            (re.compile(rf"\b{re.escape(bad)}\b", re.IGNORECASE), good)
            for bad, good in self.replacements.items()
        ]
        self._term_patterns = [
            (re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE), term)
            for term in self.terms
        ]

    @classmethod
    def load(cls, path: str) -> "Glossary":
        data = json.loads(Path(path).read_text())
        return cls(terms=data.get("terms"), replacements=data.get("replacements"))

    def apply(self, text: str) -> str:
        for pattern, good in self._replacement_patterns:
            text = pattern.sub(good, text)
        for pattern, term in self._term_patterns:
            text = pattern.sub(term, text)
        return text
