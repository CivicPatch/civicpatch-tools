import datetime
import json
import os
import secrets
import time
from typing import List, Optional, cast

from fastapi.responses import Response
from jose import jwt

from stores import redis_store

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
COOKIE_INSTANCE_URL = os.getenv("COOKIE_INSTANCE_URL", ".civicpatch.org")
APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT", "development")
IS_PRODUCTION = APP_ENVIRONMENT.lower() == "production"

SESSION_PREFIX = "session:"
SESSION_EXPIRY_DAYS = 1


# --- Redis session store ---


def _key(provider: str, provider_user_id: str) -> str:
    return f"{SESSION_PREFIX}{provider}:{provider_user_id}"


async def create_session(
    provider: str, provider_user_id: str, token: str, expires_at: float
) -> None:
    ttl = int(expires_at - time.time())
    if ttl <= 0:
        return
    entry = {"token": token, "expires_at": expires_at}
    await redis_store.set(_key(provider, provider_user_id), json.dumps(entry), ttl)


async def get_session(provider: str, provider_user_id: str) -> Optional[str]:
    raw = await redis_store.get(_key(provider, provider_user_id))
    if not raw:
        return None
    data = json.loads(raw)
    if time.time() >= data.get("expires_at", 0):
        return None
    return data["token"]


async def invalidate_session(provider: str, provider_user_id: str) -> None:
    await redis_store.delete(_key(provider, provider_user_id))


# --- Cookie helpers ---


def _get_cookie_params() -> dict:
    if IS_PRODUCTION:
        return {"domain": COOKIE_INSTANCE_URL, "secure": True}
    return {"secure": False}


async def create_session_cookies(
    response: Response, openid, teams: List[str]
) -> Response:
    """Create JWT + CSRF cookies and store session in Redis."""
    expiration = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
        days=SESSION_EXPIRY_DAYS
    )
    expires_at = expiration.timestamp()

    token = jwt.encode(
        {
            "pld": openid.model_dump(),
            "exp": expiration,
            "sub": openid.id,
            "teams": teams,
        },
        key=cast(str, JWT_SECRET_KEY),
        algorithm="HS256",
    )

    # Store in Redis for server-side invalidation
    await create_session(openid.provider, str(openid.id), token, expires_at)

    cookie_params = _get_cookie_params()

    response.set_cookie(
        key="token",
        value=token,
        expires=expiration,
        httponly=True,
        samesite="lax",
        path="/",
        **cookie_params,
    )

    # Signed CSRF token (readable by JS for double-submit)
    csrf_payload = {
        "sub": openid.id,
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(8),
    }
    csrf_signed = jwt.encode(
        csrf_payload, key=cast(str, JWT_SECRET_KEY), algorithm="HS256"
    )

    response.set_cookie(
        key="csrf_token",
        value=csrf_signed,
        expires=expiration,
        httponly=False,
        samesite="lax",
        path="/",
        **cookie_params,
    )

    return response


async def clear_session_cookies(
    response: Response,
    provider: Optional[str] = None,
    provider_user_id: Optional[str] = None,
) -> Response:
    """Remove cookies and invalidate Redis session."""
    if provider and provider_user_id:
        await invalidate_session(provider, provider_user_id)

    cookie_params = _get_cookie_params()

    response.delete_cookie(
        key="token",
        samesite="lax",
        path="/",
        **cookie_params,
    )
    response.delete_cookie(
        key="csrf_token",
        samesite="lax",
        path="/",
        **cookie_params,
    )

    return response
