"""T1.4 spike: stream an mp3 to the Live model, log every raw message with timing
and print a summary (fragment semantics, cadence, latency, glossary, GoAway).

    python -m scripts.spike_live samples/mp3/talk.mp3 --lang en
    python -m scripts.spike_live samples/mp3/talk.mp3 --lang en --loop --minutes 12

Raw log: DATA_DIR/spike/<file>-<lang>-<timestamp>-<pid>.jsonl
"""

import argparse
import asyncio
import json
import os
import statistics
import time
from pathlib import Path

from dotenv import load_dotenv

from backend.config import DEFAULT_GLOSSARY_PATH, get_settings
from backend.core.glossary import Glossary
from backend.core.metrics import rms_dbfs
from backend.engine.live_runner import LiveSessionRunner
from backend.engine.live_translate import LiveTranslateEngine
from backend.sources.base import FrameQueue, pump
from backend.sources.file_source import FileSource

VOICE_DBFS = -45.0
HANGOVER_S = 0.3
FIELDS = ("interim_input_transcription", "input_transcription", "output_transcription")


class Spike:
    def __init__(self, log_path: Path):
        self.t_start = time.monotonic()
        self.log = log_path.open("w")
        self.fragments: dict[str, list[tuple[float, str, bool | None]]] = {f: [] for f in FIELDS}
        self.voice_on: list[float] = []
        self.voice_off: list[float] = []
        self.go_aways: list[tuple[float, str]] = []
        self.other_msgs: dict[str, int] = {}
        self.frames_sent = 0
        self.error: tuple[float, str] | None = None

    def now(self) -> float:
        return time.monotonic() - self.t_start

    def write(self, record: dict) -> None:
        self.log.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.log.flush()

    async def frames(self, queue: FrameQueue):
        """Pass frames through while tracking voice on/off by energy (what the model hears)."""
        speaking = False
        last_voice = 0.0
        async for frame in queue:
            t = self.now()
            level = rms_dbfs(frame.pcm)
            if level > VOICE_DBFS:
                last_voice = t
                if not speaking:
                    speaking = True
                    self.voice_on.append(t)
                    self.write({"t": round(t, 3), "ev": "voice_on", "dbfs": round(level, 1)})
            elif speaking and t - last_voice > HANGOVER_S:
                speaking = False
                self.voice_off.append(last_voice)
                self.write({"t": round(last_voice, 3), "ev": "voice_off"})
            self.frames_sent += 1
            yield frame

    async def on_raw(self, msg) -> None:
        t = self.now()
        dump = msg.model_dump(exclude_none=True, mode="json")
        content = dump.get("server_content", {})
        for part in content.get("model_turn", {}).get("parts", []):
            if "inline_data" in part:
                part["inline_data"] = {"bytes": len(part["inline_data"].get("data") or "")}
        self.write({"t": round(t, 3), "msg": dump})
        sc = msg.server_content
        seen = False
        if sc is not None:
            for field in FIELDS:
                tr = getattr(sc, field)
                if tr is not None and (tr.text or tr.finished):
                    self.fragments[field].append((t, tr.text or "", tr.finished))
                    seen = True
            for flag in ("turn_complete", "generation_complete", "interrupted"):
                if getattr(sc, flag):
                    self.other_msgs[flag] = self.other_msgs.get(flag, 0) + 1
            if sc.model_turn:
                self.other_msgs["audio_chunks"] = self.other_msgs.get("audio_chunks", 0) + 1
                seen = True
        if msg.go_away is not None:
            self.go_aways.append((t, str(msg.go_away.time_left)))
            print(f"[{t:7.1f}s] GoAway time_left={msg.go_away.time_left}")
            seen = True
        if not seen:
            keys = ",".join(sorted(dump)) or "empty"
            self.other_msgs[keys] = self.other_msgs.get(keys, 0) + 1

    async def on_text(self, label: str, text: str) -> None:
        print(f"[{self.now():7.1f}s] {label}: {text!r}")


def _p50(values: list[float]) -> str:
    return f"{statistics.median(values) * 1000:.0f} ms (n={len(values)})" if values else "n/a"


def _next_after(times: list[float], t: float) -> float | None:
    return next((x for x in times if x >= t), None)


def summarize(spike: Spike, glossary: Glossary) -> None:
    print("\n=========== SUMMARY ===========")
    print(f"elapsed {spike.now():.1f}s, frames sent {spike.frames_sent} ({spike.frames_sent / 10:.1f}s of audio)")
    for field, frags in spike.fragments.items():
        if not frags:
            print(f"\n{field}: no messages")
            continue
        times = [t for t, _, _ in frags]
        gaps = [b - a for a, b in zip(times, times[1:])]
        lens = [len(x) for _, x, _ in frags]
        texts = [x for _, x, _ in frags if x]
        prefix = sum(1 for a, b in zip(texts, texts[1:]) if b.startswith(a) and len(b) > len(a))
        lead_space = sum(1 for x in texts if x[:1].isspace())
        finished = sum(1 for _, _, f in frags if f)
        print(f"\n{field}: {len(frags)} msgs, finished=True in {finished}")
        print(f"  gap between msgs: p50 {_p50(gaps)}, max {max(gaps, default=0):.2f}s")
        print(f"  text length: mean {statistics.mean(lens):.1f}, max {max(lens)}")
        print(f"  next starts with previous (full hypothesis): {prefix}/{max(len(texts) - 1, 1)}; "
              f"leading space (delta): {lead_space}/{len(texts)}")
        joined = "".join(texts)
        print(f"  concatenated (first 500): {joined[:500]!r}")
        applied = glossary.apply(joined)
        if applied != joined:
            print(f"  with glossary (first 500): {applied[:500]!r}")
        hits = [term for term in glossary.terms if term.lower() in joined.lower()]
        print(f"  glossary terms heard: {hits or 'none'}")

    orig_times = sorted(t for f in ("interim_input_transcription", "input_transcription")
                        for t, _, _ in spike.fragments[f])
    final_times = [t for t, _, _ in spike.fragments["input_transcription"]]
    trans_times = [t for t, _, _ in spike.fragments["output_transcription"]]
    first_partial, first_trans, end_to_final = [], [], []
    for on in spike.voice_on:
        if (n := _next_after(orig_times, on)) is not None and n - on < 10:
            first_partial.append(n - on)
        if (n := _next_after(trans_times, on)) is not None and n - on < 10:
            first_trans.append(n - on)
    for off in spike.voice_off:
        if (n := _next_after(final_times, off)) is not None and n - off < 10:
            end_to_final.append(n - off)
    print(f"\nvoice segments: {len(spike.voice_on)} (threshold {VOICE_DBFS} dBFS, hangover {HANGOVER_S}s)")
    print(f"latency voice_on -> first orig fragment: p50 {_p50(first_partial)}")
    print(f"latency voice_on -> first translation fragment: p50 {_p50(first_trans)}")
    print(f"latency voice_off -> next input_transcription: p50 {_p50(end_to_final)}")
    print(f"other messages: {spike.other_msgs}")
    print(f"go_away: {spike.go_aways or 'none'}")
    print(f"error: {spike.error or 'none'}")


async def run(args) -> None:
    settings = get_settings()
    target = "es" if args.lang == "en" else "en"
    log_dir = Path(settings.data_dir) / "spike"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{Path(args.file).stem}-{args.lang}-{int(time.time())}-{os.getpid()}.jsonl"
    spike = Spike(log_path)
    glossary = Glossary.load(DEFAULT_GLOSSARY_PATH)

    async def on_input(text: str, is_interim: bool) -> None:
        await spike.on_text("orig/interim" if is_interim else "orig", text)

    async def on_output(text: str) -> None:
        await spike.on_text("trans", text)

    runner = LiveSessionRunner(
        api_key=settings.gemini_api_key,
        model=settings.live_translate_model,
        config=LiveTranslateEngine.build_config(target),
        on_input_text=on_input,
        on_output_text=on_output,
        on_raw=spike.on_raw,
    )
    queue = FrameQueue(maxsize=50)
    producer = asyncio.create_task(pump(FileSource(args.file, loop=args.loop), queue))
    try:
        await asyncio.wait_for(runner.run(spike.frames(queue)), timeout=args.minutes * 60 or None)
    except asyncio.TimeoutError:
        print(f"\nstopped after {args.minutes} min")
    except Exception as e:
        spike.error = (round(spike.now(), 1), f"{type(e).__name__}: {e}")
        print(f"\n[{spike.now():7.1f}s] EXCEPTION {type(e).__name__}: {e}")
    finally:
        producer.cancel()
        summarize(spike, glossary)
        print(f"\nraw log: {log_path}")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="T1.4 spike: raw Live messages + measurements")
    p.add_argument("file")
    p.add_argument("--lang", choices=["en", "es"], default="en", help="source language")
    p.add_argument("--loop", action="store_true")
    p.add_argument("--minutes", type=float, default=0, help="stop after N minutes (0 = until the file ends)")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
