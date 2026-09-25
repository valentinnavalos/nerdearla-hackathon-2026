"""Knowledge Pack (T3.4), post-talk pipeline scheduling and the ask limits (T3.6)."""

import asyncio
import json

import pytest
from google.genai import errors

from backend.api.ratelimit import LRUCache, RateLimiter, normalize_question
from backend.config import Settings
from backend.core.manager import ConflictError, SessionManager
from backend.core.session import Session, SessionStatus
from backend.post import knowledge, pipeline
from tests.test_session import FakeEngine

KP = {
    "summary_es": "Resumen.",
    "summary_en": "Summary.",
    "key_points": [{"t": "00:01", "es": "punto", "en": "point"}],
    "terms": ["Kubernetes"],
    "quiz": [
        {"q_es": "¿?", "q_en": "?", "options_es": ["a", "b", "c", "d"], "options_en": ["a", "b", "c", "d"],
         "answer_idx": 2, "explanation_es": "x", "explanation_en": "x"},
        {"q_es": "mala", "q_en": "bad", "options_es": ["a"], "options_en": ["a"],
         "answer_idx": 3, "explanation_es": "x", "explanation_en": "x"},
    ],
}


class FakeResponse:
    def __init__(self, text: str):
        self.text = text


class FakeClient:
    """Stands in for genai.Client: `responses` are returned (or raised) one per call."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts: list[str] = []
        self.aio = self
        self.models = self

    async def generate_content(self, model, contents, config=None):
        self.prompts.append(contents)
        r = self.responses.pop(0)
        if isinstance(r, BaseException):
            raise r
        return FakeResponse(r)


def _rate_limited() -> errors.ClientError:
    return errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})


EVENTS = [
    {"lang": "en", "kind": "orig", "text": "hello world", "t0": 65.2},
    {"lang": "es", "kind": "trans", "text": "hola mundo", "t0": 65.2},
    {"lang": "en", "kind": "orig", "text": "  ", "t0": 70},
]


def test_transcript_for_prompt_marks_minutes_and_skips_blank_lines():
    assert knowledge.transcript_for_prompt(EVENTS, "en") == "[01:05] hello world"
    # source language empty -> falls back to the other track
    assert knowledge.source_transcript({"source_lang": "en"}, EVENTS[1:]) == "[01:05] hola mundo"


def test_generate_drops_malformed_quiz_questions_and_uses_the_glossary():
    client = FakeClient(json.dumps(KP))
    meta = {"title": "Charla", "source_lang": "en", "glossary": {"terms": ["Nerdearla"]}}
    kp = asyncio.run(knowledge.generate(client, "m", meta, EVENTS))
    assert len(kp["quiz"]) == 1 and kp["quiz"][0]["answer_idx"] == 2
    assert "Nerdearla" in client.prompts[0] and "[01:05] hello world" in client.prompts[0]


def test_generate_retries_once_after_a_429():
    client = FakeClient(_rate_limited(), json.dumps(KP))
    kp = asyncio.run(knowledge.generate(client, "m", {"source_lang": "en"}, EVENTS, retry_after_s=0))
    assert kp["summary_es"] == "Resumen."
    with pytest.raises(errors.ClientError):
        asyncio.run(knowledge.generate(FakeClient(_rate_limited(), _rate_limited()), "m",
                                       {"source_lang": "en"}, EVENTS, retry_after_s=0))


def _stopped_room(settings: Settings) -> Session:
    async def main():
        m = SessionManager(settings, engine_factory=lambda: FakeEngine(n=2), post_processor=_noop)
        s = m.create("Charla", source_lang="en")
        m.start(s.id)
        await asyncio.wait_for(s._task, timeout=2)
        return s
    return asyncio.run(main())


async def _noop(session):
    return None


@pytest.mark.parametrize("response,status", [(json.dumps(KP), "ready"), (ValueError("bad"), "error")])
def test_run_post_writes_knowledge_and_kp_status(tmp_path, monkeypatch, response, status):
    monkeypatch.setattr(knowledge, "MIN_TRANSCRIPT_WORDS", 0)  # FakeEngine only says "en 1", "en 2"
    settings = Settings(data_dir=tmp_path, gemini_api_key="k")
    session = _stopped_room(settings)
    monkeypatch.setattr(knowledge, "get_client", lambda key: FakeClient(response))
    asyncio.run(pipeline.run_post(session, settings))
    assert session.kp_status == status
    assert json.loads(session.meta_path.read_text())["kp_status"] == status
    assert session.knowledge_path.exists() == (status == "ready")


def test_run_post_without_api_key_leaves_kp_status_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge, "MIN_TRANSCRIPT_WORDS", 0)
    settings = Settings(data_dir=tmp_path, gemini_api_key="")
    session = _stopped_room(settings)
    asyncio.run(pipeline.run_post(session, settings))
    assert session.kp_status is None


def test_run_post_skips_a_too_short_transcript(tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, gemini_api_key="k")
    session = _stopped_room(settings)  # 2 two-word finals: well below MIN_TRANSCRIPT_WORDS
    monkeypatch.setattr(knowledge, "get_client", lambda key: pytest.fail("must not call Gemini"))
    asyncio.run(pipeline.run_post(session, settings))
    assert session.kp_status is None and not session.knowledge_path.exists()


def test_stop_schedules_post_without_waiting_for_it(tmp_path):
    calls: list[str] = []

    async def main():
        gate = asyncio.Event()

        async def slow_post(session):
            calls.append(session.id)
            await gate.wait()

        m = SessionManager(Settings(data_dir=tmp_path), engine_factory=lambda: FakeEngine(n=50, gap=0.05),
                           post_processor=slow_post)
        s = m.create("Charla", source_lang="en")
        m.start(s.id)
        await asyncio.sleep(0.05)
        await asyncio.wait_for(m.stop(s.id), timeout=1)  # returns while the post task is blocked
        await asyncio.sleep(0)
        assert m.post_running(s.id)
        with pytest.raises(ConflictError):
            m.regenerate(s.id)  # one pipeline per room at a time
        gate.set()
        await asyncio.sleep(0.01)
        assert not m.post_running(s.id)

        failing = m.create("Rota", source_lang="en")
        m._engine_factory = lambda: FakeEngine(n=1, fail=True)
        m.start(failing.id)
        await asyncio.wait_for(failing._task, timeout=2)
        await asyncio.sleep(0)
        assert failing.status == SessionStatus.ERROR

    asyncio.run(main())
    assert calls == ["charla"]  # the failed room never got a pipeline


def test_reload_turns_a_stale_pending_into_error(tmp_path):
    settings = Settings(data_dir=tmp_path)
    session = _stopped_room(settings)
    meta = json.loads(session.meta_path.read_text())
    meta.update(kp_status="pending", notebooklm_url="https://notebooklm.google.com/notebook/x")
    session.meta_path.write_text(json.dumps(meta))
    reloaded = SessionManager(settings, post_processor=_noop)
    reloaded.reload()
    s = reloaded.get(session.id)
    assert s.kp_status == "error"
    assert s.notebooklm_url.endswith("/x")


def test_rate_limiter_sliding_window():
    now = [0.0]
    limiter = RateLimiter(2, 10, clock=lambda: now[0])
    assert limiter.allow("ip") and limiter.allow("ip")
    assert not limiter.allow("ip")
    assert limiter.allow("other-ip")
    now[0] = 10.0
    assert limiter.allow("ip")


def test_question_normalization_and_lru_cache():
    assert normalize_question("¿Qué es  Kubernetes?") == normalize_question("que es kubernetes")
    cache = LRUCache(max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")
    cache.put("c", 3)
    assert cache.get("b") is None and cache.get("a") == 1
