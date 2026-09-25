"""T2.10a: minimal Gemini Live concurrency probe.

Deliberately independent of the backend (only google-genai + ffmpeg): N sessions in one
process with asyncio.gather, each one a sender + a receiver, every message logged. If "A works /
B is silent" reproduces here, the limit is on the Live service/quota side, not in our backend.

    python -m scripts.live_probe --sessions 1                          # baseline
    python -m scripts.live_probe --sessions 2 --trials 3               # simultaneous
    python -m scripts.live_probe --sessions 2 --stagger 10             # B starts 10 s later
    python -m scripts.live_probe --sessions 2 --model gemini-3.5-transcribe-live
    python -m scripts.live_probe --resume                              # close + resume with the handle

Raw log: DATA_DIR/probe/<timestamp>-<pid>.jsonl (first line: branch + commit + date + SDK)
"""

import argparse
import asyncio
import json
import os
import subprocess
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from scripts.report_meta import run_meta

FRAME_BYTES = 3200  # 100 ms of 16 kHz mono PCM16
FRAME_S = 0.1
DRAIN_S = 5.0
CONTENT_KINDS = {"input_transcription", "interim_input_transcription", "output_transcription", "audio", "text"}
TEXT_KINDS = ("input_transcription", "interim_input_transcription", "output_transcription")


def decode(path: str, seconds: float) -> bytes:
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-t", str(seconds), "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"]
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def build_config(model: str, target: str, resumption: bool, handle: str | None, transparent: bool):
    extra = {}
    if resumption:
        extra["session_resumption"] = types.SessionResumptionConfig(handle=handle, transparent=transparent or None)
    if "translate" in model:
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            translation_config=types.TranslationConfig(target_language_code=target, echo_target_language=False),
            **extra,
        )
    return types.LiveConnectConfig(
        response_modalities=["TEXT"],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        **extra,
    )


def classify(msg: types.LiveServerMessage) -> list[str]:
    kinds = []
    sc = msg.server_content
    if sc is not None:
        for field in TEXT_KINDS:
            tr = getattr(sc, field)
            if tr is not None and tr.text:
                kinds.append(field)
        for part in (sc.model_turn.parts or []) if sc.model_turn else []:
            if part.inline_data and part.inline_data.data:
                kinds.append("audio")
            if part.text:
                kinds.append("text")
        for flag in ("turn_complete", "generation_complete", "interrupted", "waiting_for_input"):
            if getattr(sc, flag):
                kinds.append(flag)
    for field in ("usage_metadata", "session_resumption_update", "go_away", "setup_complete"):
        if getattr(msg, field) is not None:
            kinds.append(field)
    if msg.voice_activity_detection_signal is not None or msg.voice_activity is not None:
        kinds.append("vad")
    return kinds or ["other"]


class Probe:
    def __init__(self, name: str, pcm: bytes, args, log, delay: float):
        self.name = name
        self.args = args
        self.log = log
        self.delay = delay
        self.frames = [pcm[i:i + FRAME_BYTES] for i in range(0, len(pcm), FRAME_BYTES)]
        self.next = 0
        self.t_start = 0.0
        self.counts: Counter = Counter()
        self.texts: list[dict[str, str]] = []  # per connection
        self.connect_ms: list[int] = []
        self.first_content_s: float | None = None
        self.first_text_s: float | None = None
        self.handle: str | None = None
        self.resumable = None
        self.last_consumed = None
        self.go_away: list[tuple[float, str]] = []
        self.errors: list[str] = []
        self.reconnect_gap_ms: int | None = None
        self._closed_at = 0.0

    def now(self) -> float:
        return time.monotonic() - self.t_start

    def ev(self, kind: str, **data) -> None:
        self.log.write(json.dumps({"t": round(self.now(), 3), "session": self.name, "ev": kind, **data}, ensure_ascii=False) + "\n")
        self.log.flush()

    async def run(self, client: genai.Client) -> None:
        await asyncio.sleep(self.delay)
        self.t_start = time.monotonic()
        if self.args.resume:
            mid = len(self.frames) // 2
            await self._connection(client, until=mid, handle=None)
            await self._connection(client, until=len(self.frames), handle=self.handle)
        else:
            await self._connection(client, until=len(self.frames), handle=None)

    async def _connection(self, client: genai.Client, until: int, handle: str | None) -> None:
        conn = len(self.texts) + 1
        self.texts.append({k: "" for k in TEXT_KINDS})
        config = build_config(self.args.model, self.args.target, self.args.resume, handle, self.args.transparent)
        t_connect = time.monotonic()
        self.ev("connect_start", conn=conn, resume_handle=bool(handle))
        try:
            async with client.aio.live.connect(model=self.args.model, config=config) as session:
                ms = int((time.monotonic() - t_connect) * 1000)
                self.connect_ms.append(ms)
                if conn > 1:
                    self.reconnect_gap_ms = int((time.monotonic() - self._closed_at) * 1000)
                self.ev("connected", conn=conn, ms=ms)
                receiver = asyncio.create_task(self._receive(session, conn))
                try:
                    while self.next < until and not receiver.done():
                        # absolute pacing: frames that came due during a reconnection go out right away
                        delay = self.t_start + self.next * FRAME_S - time.monotonic()
                        if delay > 0:
                            await asyncio.sleep(delay)
                        await session.send_realtime_input(
                            audio=types.Blob(data=self.frames[self.next], mime_type="audio/pcm;rate=16000")
                        )
                        self.next += 1
                    self.ev("audio_sent", conn=conn, frames=self.next)
                    if until == len(self.frames):
                        await session.send_realtime_input(audio_stream_end=True)
                        await asyncio.sleep(DRAIN_S)
                    else:
                        await asyncio.sleep(1.0)  # give the last resumption update a chance
                finally:
                    receiver.cancel()
                    (result,) = await asyncio.gather(receiver, return_exceptions=True)
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    raise result
        except Exception as e:
            self.errors.append(f"conn{conn} {type(e).__name__}: {str(e)[:160]}")
            self.ev("error", conn=conn, error=f"{type(e).__name__}: {e}")
        self._closed_at = time.monotonic()
        self.ev("close", conn=conn)

    async def _receive(self, session, conn: int) -> None:
        while True:  # receive() ends after each completed turn
            async for msg in session.receive():
                t = self.now()
                kinds = classify(msg)
                self.counts.update(kinds)
                if self.first_content_s is None and CONTENT_KINDS & set(kinds):
                    self.first_content_s = t
                record: dict = {"conn": conn, "kinds": kinds}
                sc = msg.server_content
                for field in TEXT_KINDS:
                    tr = getattr(sc, field) if sc is not None else None
                    if tr is not None and tr.text:
                        self.texts[conn - 1][field] += tr.text
                        record[field] = tr.text
                        if self.first_text_s is None:
                            self.first_text_s = t
                update = msg.session_resumption_update
                if update is not None:
                    if update.new_handle:
                        self.handle = update.new_handle
                    self.resumable = update.resumable
                    self.last_consumed = update.last_consumed_client_message_index
                    record["resumption"] = {"resumable": update.resumable,
                                            "last_consumed": update.last_consumed_client_message_index}
                if msg.go_away is not None:
                    self.go_away.append((round(t, 1), str(msg.go_away.time_left)))
                    record["go_away"] = str(msg.go_away.time_left)
                if kinds != ["audio"]:  # audio chunks are counted, not logged one by one
                    self.ev("msg", **record)


def print_table(trial: int, probes: list[Probe], args) -> None:
    print(f"\n--- trial {trial}  model={args.model}  sessions={len(probes)}  stagger={args.stagger}s")
    header = f"{'session':8} {'connect_ms':>11} {'1st_content':>11} {'1st_text':>9} {'in_frags':>8} {'out_frags':>9} {'audio':>6} {'gen_cmpl':>8} {'turn_cmpl':>9} {'resum':>6} go_away / errors"
    print(header)
    for p in probes:
        c = p.counts
        fc = f"{p.first_content_s:.1f}s" if p.first_content_s is not None else "-"
        ft = f"{p.first_text_s:.1f}s" if p.first_text_s is not None else "-"
        tail = "; ".join([f"go_away {g}" for g in p.go_away] + p.errors) or "-"
        print(f"{p.name:8} {','.join(map(str, p.connect_ms)) or '-':>11} {fc:>11} {ft:>9} "
              f"{c['input_transcription'] + c['interim_input_transcription']:>8} {c['output_transcription']:>9} "
              f"{c['audio']:>6} {c['generation_complete']:>8} {c['turn_complete']:>9} {c['session_resumption_update']:>6} {tail}")
    if args.resume:
        for p in probes:
            print(f"\n[{p.name}] resume: reconnect gap {p.reconnect_gap_ms} ms, resumable={p.resumable}, "
                  f"last_consumed_client_message_index={p.last_consumed}")
            for i, texts in enumerate(p.texts, start=1):
                orig = texts["input_transcription"] or texts["interim_input_transcription"]
                print(f"  conn{i} orig: ...{orig[-160:]!r}" if i == 1 else f"  conn{i} orig: {orig[:160]!r}...")


async def main_async(args) -> None:
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    files = args.files.split(",")
    pcms = [decode(f, args.seconds) for f in files]
    log_dir = Path(os.getenv("DATA_DIR", "data")) / "probe"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{int(time.time())}-{os.getpid()}.jsonl"
    with log_path.open("w") as log:
        log.write(json.dumps({"ev": "meta", **run_meta(args)}, default=str) + "\n")  # branch + commit + date
        for trial in range(1, args.trials + 1):
            probes = [
                Probe(chr(ord("A") + i), pcms[i % len(pcms)], args, log, delay=i * args.stagger)
                for i in range(args.sessions)
            ]
            log.write(json.dumps({"ev": "trial", "trial": trial, "model": args.model, "sessions": args.sessions,
                                  "stagger": args.stagger, "resume": args.resume}) + "\n")
            await asyncio.gather(*(p.run(client) for p in probes))
            print_table(trial, probes, args)
            if trial < args.trials:
                await asyncio.sleep(3)
    print(f"\nraw log: {log_path}")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(description="T2.10a: N concurrent Gemini Live sessions, raw SDK")
    p.add_argument("--sessions", type=int, default=2)
    p.add_argument("--seconds", type=float, default=40)
    p.add_argument("--trials", type=int, default=1)
    p.add_argument("--stagger", type=float, default=0, help="seconds between session starts")
    p.add_argument("--model", default=os.getenv("LIVE_TRANSLATE_MODEL", "gemini-3.5-live-translate-preview"))
    p.add_argument("--target", default="es", help="translation target (live-translate only)")
    p.add_argument("--files", default="samples/mp3/human-centric-eng-by-ben-popplestone.mp3",
                   help="comma-separated; session i uses file i %% len")
    p.add_argument("--resume", action="store_true", help="close at half the audio and resume with the handle")
    p.add_argument("--transparent", action="store_true", help="SessionResumptionConfig(transparent=True)")
    asyncio.run(main_async(p.parse_args()))


if __name__ == "__main__":
    main()
