"""T3.9: export a finished room to NotebookLM by hand (notebook + transcript source + podcast).

Try it locally before turning on NOTEBOOKLM_ENABLED=1 in the cloud:

    pip install -r requirements-notebooklm.txt "notebooklm-py[browser]"
    notebooklm login                                   # once: opens a browser, saves the session
    python -m scripts.notebooklm_export <session_id>   # reads DATA_DIR/sessions/<id>/
    python -m scripts.notebooklm_export <session_id> --no-audio --save

--save writes the link into meta.json (notebooklm_url), so the talk page shows the
"Abrir notebook con podcast" button after the next restart.
"""

import argparse
import asyncio
import logging
from pathlib import Path

from backend.config import configure_logging, get_settings
from backend.core.persistence import load_captions, load_json, write_json
from backend.post import exports, knowledge, notebooklm


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_id")
    parser.add_argument("--no-audio", action="store_true", help="skip the Audio Overview (faster)")
    parser.add_argument("--save", action="store_true", help="store the link in meta.json")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    if args.no_audio:
        settings.notebooklm_audio = False
    room_dir = Path(settings.data_dir) / "sessions" / args.session_id
    meta = load_json(room_dir / "meta.json")
    if meta is None:
        raise SystemExit(f"no meta.json in {room_dir}")
    events = load_captions(room_dir / "captions.jsonl")
    if not events:
        raise SystemExit(f"no captions in {room_dir}")

    kp = knowledge.load(room_dir / "knowledge.json")
    md = exports.to_md(meta, exports.group_by_lang(events), kp)
    url = await notebooklm.export(meta, md, settings)
    if url is None:
        raise SystemExit("notebooklm-py is not installed: pip install -r requirements-notebooklm.txt")
    print(url)
    if args.save:
        meta["notebooklm_url"] = url
        write_json(room_dir / "meta.json", meta)
        logging.getLogger("backend.notebooklm").info("saved to %s", room_dir / "meta.json")


if __name__ == "__main__":
    asyncio.run(main())
