from backend.config import Settings
from backend.engine.base import Engine


def create_engine(settings: Settings) -> Engine:
    """Build the engine selected by ENGINE= (imports are lazy so replay needs no API deps)."""
    name = settings.engine
    if name in ("live_translate", "chunked") and not settings.gemini_api_key:
        raise ValueError(f"ENGINE={name} necesita GEMINI_API_KEY")
    if name == "live_translate":
        from backend.engine.live_translate import LiveTranslateEngine

        return LiveTranslateEngine(
            settings.gemini_api_key,
            settings.live_translate_model,
            settings.segment_idle_s,
            rotate_after_s=settings.rotate_after_s,
        )
    if name == "chunked":
        from backend.engine.chunked import ChunkedEngine

        return ChunkedEngine(
            settings.gemini_api_key,
            settings.gemini_model,
            settings.chunk_seconds,
            settings.overlap_seconds,
        )
    if name == "replay":
        from backend.engine.replay import ReplayEngine

        return ReplayEngine(settings.replay_file)
    raise NotImplementedError(f"ENGINE={name} no está implementado (se eligió el Camino 1)")
