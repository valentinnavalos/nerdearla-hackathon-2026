from typing import Literal

from pydantic import BaseModel


class CaptionEvent(BaseModel):
    type: Literal["caption"] = "caption"
    lang: Literal["en", "es"]
    kind: Literal["orig", "trans"]
    final: bool
    text: str
    t0: float
    lat_ms: int | None = None
