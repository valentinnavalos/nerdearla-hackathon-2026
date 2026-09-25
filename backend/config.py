import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

EngineName = Literal["live_translate", "transcribe_mt", "chunked", "replay"]
Lang = Literal["en", "es"]

DEFAULT_GLOSSARY_PATH = "config/glossary.default.json"


class Settings(BaseSettings):
    """Every env var from the TASKS.md table (plus fallback A and the demo seed)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str = ""
    engine: EngineName = "live_translate"
    admin_token: str = ""
    data_dir: Path = Path("./data")
    live_translate_model: str = "gemini-3.5-live-translate-preview"
    transcribe_model: str = "gemini-3.5-transcribe-live"
    kp_model: str = "gemini-3.1-flash-lite"
    max_concurrent_live: int = 4
    rotate_after_s: int = 540
    quota_live_sessions_per_day: int = 0
    notebooklm_enabled: bool = False
    log_level: str = "INFO"
    segment_idle_s: float = 2.0  # provisional, see README "Mediciones (T1.4)"

    # fallback A (engine/chunked.py)
    gemini_model: str = "gemini-2.5-flash"
    chunk_seconds: float = 5.0
    overlap_seconds: float = 0.75
    realtime: bool = True

    replay_file: str = "samples/replay_demo.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class _SessionDefault(logging.Filter):
    """Records outside a room get `[-]` so the format never breaks."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "session"):
            record.session = "-"
        return True


def configure_logging(level: str = "INFO") -> None:
    """`HH:MM:SS LEVEL [session] message` on stderr."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(session)s] %(message)s", "%H:%M:%S"))
    handler.addFilter(_SessionDefault())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
