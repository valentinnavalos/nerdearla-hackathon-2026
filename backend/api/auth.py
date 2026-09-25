"""Admin auth (T2.5): Bearer token for REST, ?token= for WS. Same comparison either way."""

import hmac

from fastapi import HTTPException, Request, status


def _valid(configured: str, given: str | None) -> bool:
    if not configured or not given:
        return False
    return hmac.compare_digest(given, configured)


def require_admin(request: Request) -> None:
    """FastAPI dependency: 401 unless `Authorization: Bearer <ADMIN_TOKEN>` matches."""
    settings = request.app.state.settings
    header = request.headers.get("authorization", "")
    token = header[len("Bearer "):].strip() if header.startswith("Bearer ") else None
    if not _valid(settings.admin_token, token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unauthorized")


def check_ws_token(settings, token: str | None) -> bool:
    """Same check as require_admin, for WS handlers (?token=) which close the socket
    themselves instead of raising, so they can use FastAPI's own dependency injection."""
    return _valid(settings.admin_token, token)
