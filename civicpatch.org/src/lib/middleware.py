from fastapi import Request
from fastapi.responses import RedirectResponse

import database.users as user_database
import lib.auth_session as session_service

_ALLOWLISTED_PATHS = {
    "/settings",
    "/login",
    "/logout",
    "/api/permissions",
    "/api/v1/me",
}

_ALLOWLISTED_PREFIXES = (
    "/api/internal/user/display-name",
    "/api/v1/auth/",
    "/frontend/",
)


async def require_display_name(request: Request, call_next):
    if _is_allowlisted(request.url.path):
        return await call_next(request)
    if await _user_missing_display_name(request):
        return RedirectResponse("/settings", status_code=303)
    return await call_next(request)


def _is_allowlisted(path: str) -> bool:
    if path in _ALLOWLISTED_PATHS:
        return True
    return path.startswith(_ALLOWLISTED_PREFIXES)


async def _user_missing_display_name(request: Request) -> bool:
    token = request.cookies.get("token")
    if not token:
        return False
    session = await session_service.get_session(token)
    if not session:
        return False
    user_row = await user_database.get_user(
        session["provider"], session["provider_user_id"]
    )
    if not user_row:
        return False
    return not user_row.get("display_name")
