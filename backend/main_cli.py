import argparse
import asyncio
import os
import time

from dotenv import load_dotenv

from backend.engine.gemini import GeminiEngine
from backend.pipeline.chunker import chunk_frames
from backend.sources.file_source import FileSource


async def run(args) -> None:
    engine = GeminiEngine(
        os.environ["GEMINI_API_KEY"],
        os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        glossary=args.glossary.split(",") if args.glossary else None,
    )
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
        except Exception as e:  # 429s etc: report and keep going
            print(f"[{chunk.index}] ERROR {type(e).__name__}: {e}")
            continue
        e2e = time.monotonic() - chunk.t_capture
        print(f"[{chunk.index}] req={r.latency:.2f}s e2e={e2e:.2f}s")
        print(f"  EN: {r.original}\n  ES: {r.translation}")
    mins = (time.monotonic() - t_start) / 60
    print(f"\n{n} requests in {mins:.2f} min -> {n / mins:.1f} req/min")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="FileSource -> chunker -> Gemini -> console")
    p.add_argument("file")
    p.add_argument("--glossary", help="comma-separated terms, e.g. Kubernetes,Terraform")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
