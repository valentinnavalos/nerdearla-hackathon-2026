from typing import Literal

from pydantic import BaseModel


class CaptionEvent(BaseModel):
    type: Literal["caption"] = "caption"
    session_id: str
    lang: Literal["en", "es"]
    kind: Literal["orig", "trans"]
    seg: int  # id de segmento por (session, lang); interim y final comparten seg
    final: bool
    text: str
    t0: float  # segundos desde el start de la sesión
    t1: float
    lat_ms: int | None = None
