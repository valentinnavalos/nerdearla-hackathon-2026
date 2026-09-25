"""Exporter opcional a NotebookLM (T3.9, capa 2): notebook por charla + podcast (Audio Overview).

Usa `notebooklm-py`, una librería NO oficial (NotebookLM no tiene API pública para cuentas
personales): puede romperse en cualquier momento. Por eso va apagado por defecto
(NOTEBOOKLM_ENABLED=0), se importa perezosamente (no está en requirements.txt, ver
requirements-notebooklm.txt) y el pipeline solo loguea sus errores.

Auth: `notebooklm login` una vez en local (guarda storage_state.json en el perfil). En la nube,
el mismo JSON va en el secret NOTEBOOKLM_AUTH_JSON, que la librería lee sola."""

import logging

from backend.config import Settings

log = logging.getLogger("backend.notebooklm")

NOTEBOOK_TITLE = "Nerdearla 2026 — {title}"
AUDIO_TIMEOUT_S = 20 * 60  # an Audio Overview usually takes 5-10 min
AUDIO_INSTRUCTIONS = (
    "This is the live transcript of a talk at Nerdearla, a tech conference in Latin America. "
    "Explain its key ideas for attendees who want to review it, citing concrete examples from the talk."
)


def notebook_url(notebook_id: str) -> str:
    return f"https://notebooklm.google.com/notebook/{notebook_id}"


async def export(meta: dict, md: str, settings: Settings) -> str | None:
    """Create the notebook, add the transcript MD as a text source, make it public if the account
    allows it and generate the podcast. Returns the notebook link (None if the library is missing)."""
    try:
        from notebooklm import NotebookLMClient
    except ImportError:
        log.warning("NOTEBOOKLM_ENABLED=1 but notebooklm-py is not installed (pip install -r requirements-notebooklm.txt)")
        return None

    title = NOTEBOOK_TITLE.format(title=meta.get("title") or meta.get("id", "charla"))
    storage = settings.notebooklm_storage_path or None
    async with NotebookLMClient.from_storage(storage) as client:
        nb = await client.notebooks.create(title)
        log.info("notebook created: %s", nb.id)
        await client.sources.add_text(nb.id, meta.get("title") or "Transcripción", md, wait=True)

        url = notebook_url(nb.id)
        try:
            share = await client.sharing.set_public(nb.id, True)
            url = share.share_url or url
        except Exception as e:  # workspace accounts may forbid public sharing: keep the owner-only link
            log.warning("could not make notebook public: %s: %s", type(e).__name__, e)

        if settings.notebooklm_audio:
            status = await client.artifacts.generate_audio(
                nb.id, language=settings.notebooklm_audio_lang, instructions=AUDIO_INSTRUCTIONS
            )
            status = await client.artifacts.wait_for_completion(nb.id, status.task_id, timeout=AUDIO_TIMEOUT_S)
            log.info("audio overview: %s", status.status)
        return url
