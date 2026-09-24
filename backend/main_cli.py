import argparse
import asyncio
import time

from dotenv import load_dotenv

from backend.config import DEFAULT_GLOSSARY_PATH, configure_logging, get_settings
from backend.core.events import CaptionEvent
from backend.core.glossary import Glossary
from backend.core.session import other_lang
from backend.engine.base import Engine, SessionContext
from backend.engine.factory import create_engine
from backend.engine.replay import ReplayEngine
from backend.sources.base import FrameQueue, pump
from backend.sources.file_source import FileSource


def build_engine(args, settings) -> Engine:
    if args.engine == "replay":
        return ReplayEngine(args.file, loop=args.loop)
    return create_engine(settings.model_copy(update={"engine": args.engine}))


async def run(args) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = build_engine(args, settings)
    glossary = Glossary.load(args.glossary) if args.glossary else None
    ctx = SessionContext("cli", args.lang, other_lang(args.lang), glossary)

    # producer/consumer: the source keeps real-time pacing even if the engine is slow
    queue = FrameQueue(maxsize=50)
    producer = None
    if engine.needs_audio:
        source = FileSource(args.file, realtime=settings.realtime, loop=args.loop)
        producer = asyncio.create_task(pump(source, queue))
    else:
        queue.close()

    t_start = time.monotonic()

    async def emit(event: CaptionEvent) -> None:
        marker = "FINAL" if event.final else "interim"
        lat = f" lat={event.lat_ms}ms" if event.lat_ms is not None else ""
        print(f"[{time.monotonic() - t_start:6.1f}s] {event.lang}/{event.kind}/{marker} "
              f"seg={event.seg}{lat}: {event.text}")

    try:
        await engine.run(queue, emit, ctx)
    finally:
        if producer:
            producer.cancel()
        print(f"\n{time.monotonic() - t_start:.1f}s elapsed, dropped_frames={queue.dropped_frames}")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="FileSource -> engine -> console")
    p.add_argument("file", help="audio file (or a captions .jsonl with --engine replay)")
    p.add_argument(
        "--engine",
        choices=["live_translate", "chunked", "replay"],
        default=get_settings().engine,
    )
    p.add_argument("--lang", choices=["en", "es"], default="en", help="source language")
    p.add_argument("--loop", action="store_true", help="loop the file")
    p.add_argument(
        "--glossary",
        default=DEFAULT_GLOSSARY_PATH,
        help="path to a glossary JSON file ({\"terms\": [...], \"replacements\": {...}})",
    )
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
