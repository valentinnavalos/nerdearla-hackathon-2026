"""T2.10a at runner level: N LiveTranslateEngine sessions in one process with our own runner,
segmenter, glossary and FrameQueue (still no FastAPI/WS). Compare with scripts/live_probe.py
(raw SDK): if both sessions work here too, our runner is not the bottleneck.

    python -m scripts.runner_probe samples/mp3/human-centric-eng-by-ben-popplestone.mp3:en \\
        samples/es_talk_2min.mp3:es --seconds 45
"""

import argparse
import asyncio
import time
from collections import Counter

from dotenv import load_dotenv

from backend.config import DEFAULT_GLOSSARY_PATH, configure_logging, get_settings
from backend.core.glossary import Glossary
from backend.core.session import other_lang
from backend.engine.base import SessionContext
from backend.engine.factory import create_engine
from backend.sources.base import FrameQueue, pump
from backend.sources.file_source import FileSource


async def run_one(name: str, path: str, lang: str, seconds: float) -> dict:
    settings = get_settings().model_copy(update={"engine": "live_translate"})
    engine = create_engine(settings)
    ctx = SessionContext(name, lang, other_lang(lang), Glossary.load(DEFAULT_GLOSSARY_PATH))
    queue = FrameQueue(maxsize=50)
    producer = asyncio.create_task(pump(FileSource(path), queue))
    finals: Counter = Counter()

    async def emit(event) -> None:
        if event.final:
            finals[event.kind] += 1

    t0 = time.monotonic()
    try:
        await asyncio.wait_for(engine.run(queue, emit, ctx), timeout=seconds)
        outcome = "ended"
    except asyncio.TimeoutError:
        outcome = f"cut at {seconds:.0f}s"
    except Exception as e:
        outcome = f"{type(e).__name__}: {e}"
    finally:
        producer.cancel()
    return {
        "name": name,
        "lang": lang,
        "elapsed": time.monotonic() - t0,
        "stats": engine.runner.stats if engine.runner else {},
        "finals": finals,
        "dropped": queue.dropped_frames,
        "outcome": outcome,
    }


def print_table(results: list[dict]) -> None:
    print(f"\n{'session':8} {'lang':4} {'connect_ms':>10} {'1st_text':>8} {'msgs/s':>7} "
          f"{'fin_orig':>8} {'fin_trans':>9} {'dropped':>7} {'dispatch_max':>12}  outcome")
    for r in results:
        st = r["stats"]
        first = f"{st['first_text_s']:.1f}s" if st.get("first_text_s") is not None else "-"
        rate = st.get("msgs", 0) / r["elapsed"] if r["elapsed"] else 0
        print(f"{r['name']:8} {r['lang']:4} {st.get('connect_ms') or '-':>10} {first:>8} {rate:>7.1f} "
              f"{r['finals']['orig']:>8} {r['finals']['trans']:>9} {r['dropped']:>7} "
              f"{st.get('dispatch_ms_max', 0):>10.1f}ms  {r['outcome']}")


async def main_async(args) -> None:
    configure_logging(get_settings().log_level)
    jobs = []
    for i, item in enumerate(args.inputs):
        path, _, lang = item.rpartition(":")
        jobs.append(run_one(chr(ord("A") + i), path, lang, args.seconds))
    print_table(await asyncio.gather(*jobs))


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="T2.10a: N LiveTranslateEngine sessions in one process")
    p.add_argument("inputs", nargs="+", help="audio_file:lang (lang = en | es)")
    p.add_argument("--seconds", type=float, default=45, help="cut every session after N seconds")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
