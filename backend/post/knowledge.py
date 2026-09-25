"""Knowledge Pack (T3.4) + "Preguntale a la charla" (T3.6): una llamada a KP_MODEL sobre la
transcripción entera (~10k tokens para 40 min, entra completa en contexto)."""

import asyncio
import json
import logging
from functools import lru_cache
from pathlib import Path

from google import genai
from google.genai import errors, types

from backend.core.persistence import load_json, write_json
from backend.post.exports import fmt_mmss

log = logging.getLogger("backend.knowledge")

RETRY_AFTER_S = 60.0
# below this the model has nothing to summarize and starts inventing (seen with a 4 s test room)
MIN_TRANSCRIPT_WORDS = 60
ASK_MAX_CHARS = 300

_NO_AFC = types.AutomaticFunctionCallingConfig(disable=True)  # no tools here; also silences its warning
_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": _STR}

SCHEMA = {
    "type": "object",
    "properties": {
        "summary_es": _STR,
        "summary_en": _STR,
        "key_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"t": _STR, "es": _STR, "en": _STR},
                "required": ["t", "es", "en"],
            },
        },
        "terms": _STR_LIST,
        "quiz": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "q_es": _STR,
                    "q_en": _STR,
                    "options_es": _STR_LIST,
                    "options_en": _STR_LIST,
                    "answer_idx": {"type": "integer"},
                    "explanation_es": _STR,
                    "explanation_en": _STR,
                },
                "required": ["q_es", "q_en", "options_es", "options_en", "answer_idx",
                             "explanation_es", "explanation_en"],
            },
        },
    },
    "required": ["summary_es", "summary_en", "key_points", "terms", "quiz"],
}

KP_PROMPT = """You are preparing the post-talk "Knowledge Pack" for a tech conference (Nerdearla).
Talk: "{title}"{speaker}. Below is the live transcript, one line per segment, prefixed with [mm:ss].
{glossary}
Produce, in both neutral Spanish (es) and English (en):
- summary_es / summary_en: 5-7 sentences each (shorter if the talk is short).
- key_points: 5-8 items; "t" is the [mm:ss] (without brackets) where the point is made.
- terms: technical terms and product names mentioned (as spoken, no translation).
- quiz: 5 multiple-choice questions, 4 options each, answer_idx is 0-3,
  with a one-sentence explanation.
Use ONLY what is said in the transcript: never add tools, facts or topics that are not in it, even
if the title suggests them. If the transcript is short, return fewer key points and quiz questions.
The transcript comes from live speech recognition: silently fix obvious recognition errors.

Transcript:
{transcript}"""

ASK_PROMPT = """You answer questions from the audience about a tech conference talk, "{title}"{speaker}.
Use ONLY the transcript below (lines prefixed with [mm:ss]). Answer in the same language as the
question, in 1-4 sentences, and cite the minute(s) like [mm:ss]. If the talk does not cover it,
say so plainly (in the question's language) instead of guessing.

Transcript:
{transcript}

Question: {question}"""


@lru_cache
def get_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def transcript_for_prompt(events: list[dict], lang: str) -> str:
    """`[mm:ss] text` lines from the finals of one language (the original track by default)."""
    return "\n".join(
        f"[{fmt_mmss(e['t0'])}] {e['text'].strip()}"
        for e in events
        if e.get("lang") == lang and e.get("text", "").strip()
    )


def source_transcript(meta: dict, events: list[dict]) -> str:
    """Transcript in the talk's source language; falls back to the other one if it came out empty."""
    source_lang = meta.get("source_lang") or "en"
    text = transcript_for_prompt(events, source_lang)
    if not text:
        other = "es" if source_lang == "en" else "en"
        text = transcript_for_prompt(events, other)
    return text


def long_enough(meta: dict, events: list[dict]) -> bool:
    return len(source_transcript(meta, events).split()) >= MIN_TRANSCRIPT_WORDS


def _speaker(meta: dict) -> str:
    return f" by {meta['speaker']}" if meta.get("speaker") else ""


def _glossary(meta: dict) -> str:
    terms = (meta.get("glossary") or {}).get("terms") or []
    return f"Glossary (spell these exactly): {', '.join(terms)}.\n" if terms else ""


def is_overloaded(e: BaseException) -> bool:
    """429 (quota) or 503 ("model is experiencing high demand"): both clear up by waiting."""
    return isinstance(e, errors.APIError) and e.code in (429, 503)


async def _generate_json(client: genai.Client, model: str, prompt: str) -> dict:
    resp = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SCHEMA,
            temperature=0.3,
            automatic_function_calling=_NO_AFC,
        ),
    )
    return json.loads(resp.text or "{}")


def _validate(data: dict) -> dict:
    """Keep only well-formed quiz questions; the rest of the schema is enforced by the API."""
    quiz = []
    for q in data.get("quiz") or []:
        opts_es, opts_en = q.get("options_es") or [], q.get("options_en") or []
        idx = q.get("answer_idx")
        if isinstance(idx, int) and 0 <= idx < min(len(opts_es), len(opts_en)):
            quiz.append(q)
    data["quiz"] = quiz
    return data


async def generate(
    client: genai.Client,
    model: str,
    meta: dict,
    events: list[dict],
    retry_after_s: float = RETRY_AFTER_S,
) -> dict:
    """One call to KP_MODEL; on a 429/503 it waits and retries once, then lets the error through."""
    transcript = source_transcript(meta, events)
    if not transcript:
        raise ValueError("la transcripción está vacía")
    prompt = KP_PROMPT.format(
        title=meta.get("title", ""), speaker=_speaker(meta), glossary=_glossary(meta), transcript=transcript
    )
    try:
        data = await _generate_json(client, model, prompt)
    except errors.APIError as e:
        if not is_overloaded(e):
            raise
        log.warning("knowledge pack got %s, retrying in %.0f s", e.code, retry_after_s)
        await asyncio.sleep(retry_after_s)
        data = await _generate_json(client, model, prompt)
    return _validate(data)


async def ask(client: genai.Client, model: str, meta: dict, transcript: str, question: str) -> str:
    prompt = ASK_PROMPT.format(
        title=meta.get("title", ""), speaker=_speaker(meta), transcript=transcript, question=question
    )
    resp = await client.aio.models.generate_content(
        model=model, contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2, automatic_function_calling=_NO_AFC),
    )
    return (resp.text or "").strip()


def save(path: Path, data: dict) -> None:
    write_json(path, data)


def load(path: Path | None) -> dict | None:
    return load_json(path) if path else None
