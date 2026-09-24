import argparse
import asyncio
import os
import time
from typing import AsyncIterator

from dotenv import load_dotenv

from backend.core.events import CaptionEvent
from backend.core.glossary import Glossary
from backend.engine.base import Engine
from backend.sources.base import AudioFrame
from backend.sources.file_source import FileSource

DEFAULT_GLOSSARY_PATH = "config/glossary.default.json"


def build_engine(args, glossary: Glossary | None) -> Engine:
    if args.engine == "chunked":
        from backend.engine.chunked import GeminiEngine

        return GeminiEngine(
            os.environ["GEMINI_API_KEY"],
            os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            glossary=glossary.terms if glossary else None,
        )
    from backend.engine.live_translate import LiveTranslateEngine

    return LiveTranslateEngine(
        os.environ["GEMINI_API_KEY"],
        os.getenv("LIVE_TRANSLATE_MODEL", "gemini-3.5-live-translate-preview"),
        source_lang=args.lang,
        glossary=glossary,
    )


async def queued_frames(source: FileSource, queue: "asyncio.Queue[AudioFrame | None]") -> None:
    async for frame in source.frames():
        if queue.full():
            queue.get_nowait()  # drop the oldest frame instead of blocking the pacing
        await queue.put(frame)
    await queue.put(None)


async def from_queue(queue: "asyncio.Queue[AudioFrame | None]") -> AsyncIterator[AudioFrame]:
    while True:
        frame = await queue.get()
        if frame is None:
            return
        yield frame


async def run_chunked(args, engine) -> None:
    from backend.pipeline.chunker import chunk_frames

    source = FileSource(args.file, realtime=os.getenv("REALTIME", "1") == "1")
    chunks = chunk_frames(
        source.frames(),
        float(os.getenv("CHUNK_SECONDS", "5")),
        float(os.getenv("OVERLAP_SECONDS", "0.75")),
    )
    t_start = time.monotonic()
    n = 0
    async for chunk in chunks:
        n += 1
        try:
            r = await engine.transcribe_translate(chunk.pcm)
        except Exception as e:
            print(f"[{chunk.index}] ERROR {type(e).__name__}: {e}")
            continue
        e2e = time.monotonic() - chunk.t_capture
        print(f"[{chunk.index}] req={r.latency:.2f}s e2e={e2e:.2f}s")
        print(f"  EN: {r.original}\n  ES: {r.translation}")
    mins = (time.monotonic() - t_start) / 60
    print(f"\n{n} requests in {mins:.2f} min -> {n / mins:.1f} req/min")


async def run_live(args, engine: Engine) -> None:
    source = FileSource(
        args.file,
        realtime=os.getenv("REALTIME", "1") == "1",
        loop=args.loop,
    )
    queue: "asyncio.Queue[AudioFrame | None]" = asyncio.Queue(maxsize=50)
    producer = asyncio.create_task(queued_frames(source, queue))

    async def emit(event: CaptionEvent) -> None:
        marker = "FINAL" if event.final else "interim"
        print(f"[{event.t0:6.2f}s] {event.lang}/{event.kind}/{marker}: {event.text}")

    try:
        await engine.run(from_queue(queue), emit)
    finally:
        producer.cancel()


async def run(args) -> None:
    glossary = Glossary.load(args.glossary) if args.glossary else None
    engine = build_engine(args, glossary)
    if args.engine == "chunked":
        await run_chunked(args, engine)
    else:
        await run_live(args, engine)


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="FileSource -> Gemini engine -> console")
    p.add_argument("file")
    p.add_argument(
        "--engine",
        choices=["live_translate", "chunked"],
        default=os.getenv("ENGINE", "live_translate"),
    )
    p.add_argument("--lang", choices=["en", "es"], default="en", help="source language")
    p.add_argument("--loop", action="store_true", help="loop the file (live engines only)")
    p.add_argument(
        "--glossary",
        default=DEFAULT_GLOSSARY_PATH if os.path.exists(DEFAULT_GLOSSARY_PATH) else None,
        help="path to a glossary JSON file ({\"terms\": [...], \"replacements\": {...}})",
    )
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
