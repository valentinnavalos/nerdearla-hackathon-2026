import pytest


@pytest.fixture(autouse=True)
def _no_real_post_talk_calls(monkeypatch):
    """Settings also reads .env: without this, a developer's real GEMINI_API_KEY would make every
    stopped test room call Gemini for its Knowledge Pack (T3.4) or NotebookLM (T3.9)."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("NOTEBOOKLM_ENABLED", "0")
