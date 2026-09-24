# Nerdearla Hackathon 2026 — live EN→ES interpreter

Step 1: `FileSource → chunker → Gemini → console`, to validate latency and quota.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add GEMINI_API_KEY
```

Needs `ffmpeg`. Put 3-5 min of English audio in `samples/` (e.g. with `yt-dlp -x`).

## Run

```bash
python -m backend.main_cli samples/talk.mp3
python -m backend.main_cli samples/talk.mp3 --glossary Kubernetes,Terraform
```

Config via env: `GEMINI_MODEL`, `CHUNK_SECONDS`, `OVERLAP_SECONDS`, `REALTIME`.

## Step 1 metrics

| Metric | Threshold | Result |
|---|---|---|
| Latency per request | < 2-3 s | |
| Technical terms (with/without glossary) | "Kubernetes" not "cubernetes" | |
| Requests/min, 1 session | below real RPM | |
| 2 simultaneous processes | no 429 | |

## License

MIT
