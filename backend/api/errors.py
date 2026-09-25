"""Domain errors -> HTTP answers, registered on the app so every endpoint maps them the same way."""

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.core.capacity import CapacityError


async def capacity_error_handler(request: Request, exc: CapacityError) -> JSONResponse:
    """409: the room exists but there is no free Live slot to start it (T2.5)."""
    manager = getattr(request.app.state, "manager", None)
    body = {"detail": str(exc)}
    if manager is not None:
        body["live"] = manager.live_usage()
    return JSONResponse(status_code=409, content=body)
