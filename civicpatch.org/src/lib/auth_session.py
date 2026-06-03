import datetime
import json
import secrets
import time
from typing import List, Optional

from fastapi.responses import Response

import lib.redis as redis_store
import environment

SESSION_EXPIRY_DAYS = 7

_TOKEN_PREFIX = "session:tok:"
_USER_PREFIX = "session:usr:"


def _token_key(token: str) -> str:
    return f"{_TOKEN_PREFIX}{token}"


def _user_key(provider: str, provider_user_id: str) -> str:
    return f"{_USER_PREFIX}{provider}:{provider_user_id}"


# --- Redis session store ---


async def create_session(
    token: str,
    provider: str,
    provider_user_id: str,
    email: Optional[str],
    teams: List[str],
    expires_at: float,
) -> None:
    ttl = int(expires_at - time.time())
    if ttl <= 0:
        return
    entry = {
        "provider": provider,
        "provider_user_id": provider_user_id,
        "email": email,
        "teams": teams,
        "expires_at": expires_at,
    }
    await redis_store.set(_token_key(token), json.dumps(entry), ttl)
    await redis_store.set(_user_key(provider, provider_user_id), token, ttl)


async def get_session(token: str) -> Optional[dict]:
    raw = await redis_store.get(_token_key(token))
    if not raw:
        return None
    data = json.loads(raw)
    if time.time() >= data.get("expires_at", 0):
        return None
    return data


async def invalidate_session(provider: str, provider_user_id: str) -> None:
    token = await redis_store.get(_user_key(provider, provider_user_id))
    if token:
        await redis_store.delete(_token_key(token))
    await redis_store.delete(_user_key(provider, provider_user_id))


# --- Cookie helpers ---


def _get_cookie_params() -> dict:
    env = environment.get_env_vars()
    app_environment = env.get("APP_ENVIRONMENT", "development")
    is_production = app_environment.lower() == "production"
    if is_production:
        return {"domain": env.get("COOKIE_INSTANCE_URL", ".civicpatch.org"), "secure": True}
    return {"secure": False}


async def create_session_cookies(
    response: Response, openid, teams: List[str]
) -> Response:
    """Create opaque session token + CSRF nonce cookies and store session in Redis."""
    expiration = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
        days=SESSION_EXPIRY_DAYS
    )
    expires_at = expiration.timestamp()

    token = secrets.token_urlsafe(32)
    csrf_nonce = secrets.token_urlsafe(24)

    await create_session(
        token=token,
        provider=openid.provider,
        provider_user_id=str(openid.id),
        email=openid.email,
        teams=teams,
        expires_at=expires_at,
    )

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

    # JS-readable CSRF nonce for double-submit pattern
    response.set_cookie(
        key="csrf_token",
        value=csrf_nonce,
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
