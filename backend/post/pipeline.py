"""Post-talk pipeline: runs in the background once a room stops (T3.4, T3.9).

Never on the Stop critical path: SessionManager schedules it as its own task, and any failure
only lands in kp_status/logs - the exports keep working from captions.jsonl either way."""

import asyncio

from backend.config import Settings
from backend.core.persistence import load_captions
from backend.core.session import Session
from backend.post import exports, knowledge, notebooklm


async def _persist(session: Session) -> None:
    try:
        await asyncio.to_thread(session.save_meta)
    except OSError as e:
        session.log.error("meta.json write failed: %s", e)


async def run_post(session: Session, settings: Settings) -> None:
    events = await asyncio.to_thread(load_captions, session.captions_path) if session.captions_path else []
    if not any(e.get("text", "").strip() for e in events):
        session.log.info("post-talk: no captions, skipping")
        return
    meta = session.meta()

    kp = None
    if not knowledge.long_enough(meta, events):
        session.log.info("post-talk: transcript too short for a knowledge pack, skipping")
    elif settings.gemini_api_key:
        session.kp_status = "pending"
        await _persist(session)
        try:
            client = knowledge.get_client(settings.gemini_api_key)
            kp = await knowledge.generate(client, settings.kp_model, meta, events)
            await asyncio.to_thread(knowledge.save, session.knowledge_path, kp)
            session.kp_status = "ready"
            session.log.info("knowledge pack ready (%d key points, %d quiz)",
                             len(kp.get("key_points", [])), len(kp.get("quiz", [])))
        except Exception as e:
            session.kp_status = "error"
            session.log.warning("knowledge pack failed: %s: %s", type(e).__name__, e)
        await _persist(session)
    else:
        session.log.info("post-talk: no GEMINI_API_KEY, skipping knowledge pack")

    if settings.notebooklm_enabled:
        try:
            md = exports.to_md(meta, exports.group_by_lang(events), kp)
            url = await notebooklm.export(meta, md, settings)
            if url:
                session.notebooklm_url = url
                await _persist(session)
        except Exception as e:  # unofficial library: it can break at any time, never take anything down
            session.log.warning("notebooklm export failed: %s: %s", type(e).__name__, e)
