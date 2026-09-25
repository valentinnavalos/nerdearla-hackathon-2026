"""Exports SRT/VTT/TXT/MD a partir de captions.jsonl + meta.json (T3.3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

MAX_LINE_CHARS = 42
MAX_LINES = 2
MAX_CUE_CHARS = MAX_LINE_CHARS * MAX_LINES
MAX_CUE_S = 7.0
MIN_CUE_S = 1.0
# Nerdearla is in Buenos Aires (no DST); a fixed offset needs no tzdata in the slim image
TALK_TZ = timezone(timedelta(hours=-3), "ART")


@dataclass
class Cue:
    t0: float
    t1: float
    text: str


def median_latency_ms(events: list[dict]) -> float:
    """p50 de lat_ms sobre los eventos finales que lo traen (0 si no hay datos).

    Se calcula a partir de lo ya guardado en captions.jsonl en vez de leer
    SessionContext.metrics: así el export funciona igual con la sesión parada
    o recargada tras un restart del proceso.
    """
    values = sorted(e["lat_ms"] for e in events if e.get("lat_ms") is not None)
    if not values:
        return 0.0
    mid = len(values) // 2
    if len(values) % 2:
        return float(values[mid])
    return (values[mid - 1] + values[mid]) / 2.0


def _wrap_lines(text: str, max_chars: int = MAX_LINE_CHARS, max_lines: int = MAX_LINES) -> list[str]:
    """Envuelve texto en como máximo max_lines líneas de max_chars, cortando en espacios."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == max_lines - 1 and current:
            # última línea permitida: que junte el resto sin volver a cortar de más
            continue
    if current:
        lines.append(current)
    return lines[:max_lines]


def _split_chunks(text: str, max_chars: int = MAX_CUE_CHARS) -> list[str]:
    """Parte un texto largo en trozos de hasta max_chars caracteres, cortando en espacios."""
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks or [text]


def build_cues(events: list[dict], offset_ms: float = 0.0) -> list[Cue]:
    """Convierte eventos finales (de un lang) en cues con límites de largo/duración.

    - Máximo 42 caracteres por línea, 2 líneas por cue.
    - Duración máxima 7 s, mínima 1 s.
    - Un final que no entra en un cue se parte en varios, repartiendo el
      tiempo proporcionalmente a la cantidad de caracteres de cada parte.
    - offset_ms se resta a cada timestamp (compensa la latencia del pipeline).
    """
    offset_s = offset_ms / 1000.0
    cues: list[Cue] = []
    for event in events:
        text = event["text"].strip()
        if not text:
            continue
        t0 = max(0.0, event["t0"] - offset_s)
        t1 = max(t0, event["t1"] - offset_s)
        duration = max(t1 - t0, 0.0)
        chunks = _split_chunks(text)
        total_chars = sum(len(c) for c in chunks) or 1
        cursor = t0
        for chunk in chunks:
            share = len(chunk) / total_chars
            chunk_duration = duration * share
            chunk_duration = min(max(chunk_duration, MIN_CUE_S), MAX_CUE_S)
            cue_t0 = cursor
            cue_t1 = cue_t0 + chunk_duration
            cues.append(Cue(t0=cue_t0, t1=cue_t1, text="\n".join(_wrap_lines(chunk))))
            cursor = cue_t1
    # nunca dejar que un cue empiece antes de que termine el anterior
    for prev, nxt in zip(cues, cues[1:]):
        if nxt.t0 < prev.t1:
            nxt.t0 = prev.t1
            if nxt.t1 < nxt.t0 + MIN_CUE_S:
                nxt.t1 = nxt.t0 + MIN_CUE_S
    return cues


def _fmt_timestamp(seconds: float, ms_sep: str) -> str:
    seconds = max(0.0, seconds)
    total_ms = round(seconds * 1000)
    h, rem_ms = divmod(total_ms, 3_600_000)
    m, rem_ms = divmod(rem_ms, 60_000)
    s, ms = divmod(rem_ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d}{ms_sep}{ms:03d}"


def fmt_mmss(seconds: float) -> str:
    seconds = max(0, round(seconds))
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"


def to_srt(cues: list[Cue]) -> str:
    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        lines.append(f"{_fmt_timestamp(cue.t0, ',')} --> {_fmt_timestamp(cue.t1, ',')}")
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def to_vtt(cues: list[Cue]) -> str:
    lines = ["WEBVTT", ""]
    for cue in cues:
        lines.append(f"{_fmt_timestamp(cue.t0, '.')} --> {_fmt_timestamp(cue.t1, '.')}")
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def to_txt(events: list[dict]) -> str:
    return "\n".join(e["text"].strip() for e in events if e.get("text", "").strip()) + "\n"


def _fmt_datetime(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, TALK_TZ).strftime("%Y-%m-%d %H:%M (%Z)")


def group_by_lang(events: list[dict]) -> dict[str, list[dict]]:
    events_by_lang: dict[str, list[dict]] = {}
    for e in events:
        events_by_lang.setdefault(e["lang"], []).append(e)
    return events_by_lang


def _knowledge_md(knowledge: dict) -> list[str]:
    """Resumen + puntos clave del Knowledge Pack (T3.4) al tope del MD, para que la
    fuente que se pega en NotebookLM ya traiga el contexto (capa 3)."""
    lines: list[str] = []
    for key, label in (("summary_es", "Resumen"), ("summary_en", "Summary")):
        if knowledge.get(key):
            lines += [f"## {label}", "", knowledge[key].strip(), ""]
    points = knowledge.get("key_points") or []
    if points:
        lines += ["## Puntos clave · Key points", ""]
        for p in points:
            lines.append(f"- [{p.get('t', '')}] {p.get('es', '')} / {p.get('en', '')}")
        lines.append("")
    terms = knowledge.get("terms") or []
    if terms:
        lines += [f"**Términos:** {', '.join(terms)}", ""]
    return lines


def to_md(meta: dict, events_by_lang: dict[str, list[dict]], knowledge: dict | None = None) -> str:
    lines = [f"# {meta.get('title', 'Charla')}"]
    speaker = meta.get("speaker")
    if speaker:
        lines.append(f"**Orador:** {speaker}")
    source_lang = meta.get("source_lang")
    target_lang = meta.get("target_lang")
    if source_lang and target_lang:
        lines.append(f"**Idiomas:** {source_lang} → {target_lang}")
    if meta.get("started_at"):
        lines.append(f"**Inicio:** {_fmt_datetime(meta['started_at'])}")
    if meta.get("stopped_at"):
        lines.append(f"**Fin:** {_fmt_datetime(meta['stopped_at'])}")
    lines.append("")
    if knowledge:
        lines += _knowledge_md(knowledge)
    for lang in sorted(events_by_lang):
        events = events_by_lang[lang]
        if not events:
            continue
        lines.append(f"## Transcripción ({lang})")
        lines.append("")
        for e in events:
            text = e["text"].strip()
            if not text:
                continue
            lines.append(f"[{fmt_mmss(e['t0'])}] {text}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"
