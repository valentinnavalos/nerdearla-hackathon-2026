import json
import re
from pathlib import Path


def _word(text: str) -> re.Pattern:
    # lookarounds instead of \b so terms like "C++" or ".NET" still match as whole words
    return re.compile(rf"(?<!\w){re.escape(text)}(?!\w)", re.IGNORECASE)


class Glossary:
    """Loads terms/replacements and normalizes text against them."""

    def __init__(self, terms: list[str] | None = None, replacements: dict[str, str] | None = None):
        self.terms = terms or []
        self.replacements = replacements or {}
        # longest first, so "nerd earla" wins over a shorter overlapping entry
        self._replacement_patterns = [
            (_word(bad), good)
            for bad, good in sorted(self.replacements.items(), key=lambda kv: -len(kv[0]))
        ]
        self._term_patterns = [(_word(term), term) for term in self.terms]

    @classmethod
    def load(cls, path: str) -> "Glossary":
        data = json.loads(Path(path).read_text())
        return cls(terms=data.get("terms"), replacements=data.get("replacements"))

    @classmethod
    def parse_text(cls, text: str) -> "Glossary":
        """Operator textarea format: one term per line, `wrong => right` for a replacement."""
        terms: list[str] = []
        replacements: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=>" in line:
                bad, good = (part.strip() for part in line.split("=>", 1))
                if bad and good:
                    replacements[bad] = good
            else:
                terms.append(line)
        return cls(terms=terms, replacements=replacements)

    @classmethod
    def merge(cls, base: "Glossary | None", session: "Glossary | None") -> "Glossary":
        """Default glossary + the session's one; on conflicts the session wins."""
        base = base or cls()
        session = session or cls()
        seen = {t.lower() for t in session.terms}
        terms = session.terms + [t for t in base.terms if t.lower() not in seen]
        replacements = {k.lower(): v for k, v in base.replacements.items()}
        replacements.update({k.lower(): v for k, v in session.replacements.items()})
        return cls(terms=terms, replacements=replacements)

    def to_dict(self) -> dict:
        return {"terms": self.terms, "replacements": self.replacements}

    def apply(self, text: str) -> str:
        for pattern, good in self._replacement_patterns:
            text = pattern.sub(good, text)
        for pattern, term in self._term_patterns:
            text = pattern.sub(term, text)
        return text
