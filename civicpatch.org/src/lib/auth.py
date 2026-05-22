import logging
from typing import cast, Optional

from fastapi import Depends, HTTPException, Request, Security, WebSocket
from fastapi.security import APIKeyCookie, APIKeyHeader

import database.users as database
import environment
from schemas.common import Identity, Role, RouteCategory, has_at_least
import lib.auth_session as session_service

logger = logging.getLogger(__name__)

API_COOKIE = APIKeyCookie(name="token", auto_error=False)
API_HEADER = APIKeyHeader(name="Authorization", auto_error=False)

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


async def get_user(
    request: Request,
    authorization: Optional[str] = Security(API_HEADER),
    cookie: Optional[str] = Security(API_COOKIE),
) -> Identity:
    env = environment.get_env_vars()
    service_api_key = env.get("SERVICE_API_KEY")

    token = None
    token_source = None

    # 1. Prioritize cookie if present
    if cookie:
        token = cookie
        token_source = "cookie"
    # 2. Then check Authorization header
    elif authorization:
        token = authorization.strip()
        # Check if it's the service API key
        if service_api_key and token == service_api_key:
            token_source = "service_api_key"
        else:
            token_source = "header"
    else:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    # 3. Handle service API key — distinct from human identities; no role.
    # The type-based bypass in `require_route_access` is what gates its access.
    if token_source == "service_api_key":
        return Identity(
            type="service_api_key",
            provider="system",
            provider_user_id="service_api_key",
            email="service@civicpatch.org",
        )

    try:
        if token_source == "cookie":
            identity = await get_user_by_cookie(request, token)
        elif token_source == "header":
            identity = await get_user_by_api_key(token)
        else:
            raise HTTPException(
                status_code=401, detail=f"Unknown token source: {token_source}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=401, detail=f"Failed to construct identity object: {e}"
        )

    return identity


# Update Identity creation to use teams (list)
async def get_user_by_api_key(api_key: str) -> Identity:
    user = await database.get_user_by_api_key(api_key)

    if not user:
        raise HTTPException(status_code=401, detail="No identity found using api key")

    return Identity(
        type="user_key",
        provider=cast(str, user.get("provider")),
        provider_user_id=cast(str, user.get("provider_user_id")),
        email=user.get("email"),
        role=user.get("role", Role.DEFAULT.value),
        user_id=user.get("id"),
    )


async def get_user_by_cookie(request, token: str) -> Identity:
    session = await session_service.get_session(token)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalidated")

    if request.method.upper() in UNSAFE_METHODS:
        csrf_header = request.headers.get("x-csrf-token")
        if not csrf_header:
            form = await request.form()
            csrf_header = form.get("csrf_token")

        csrf_cookie = request.cookies.get("csrf_token")
        if not csrf_header or not csrf_cookie or csrf_header != csrf_cookie:
            logger.debug(
                f"CSRF double-submit failed: has_header={bool(csrf_header)}, has_cookie={bool(csrf_cookie)}"
            )
            raise HTTPException(
                status_code=403,
                detail="CSRF check failed for cookie-authenticated request",
            )

    provider = session["provider"]
    provider_user_id = session["provider_user_id"]
    user_row = await database.get_user(provider, provider_user_id)
    # Trust the DB role over the session-cached role — session can be stale after a grant.
    role = (user_row.get("role") if user_row else None) or session.get("role") or Role.DEFAULT.value

    return Identity(
        type="cookie",
        provider=provider,
        provider_user_id=provider_user_id,
        email=session.get("email"),
        role=role,
        user_id=user_row.get("id") if user_row else None,
        display_name=user_row.get("display_name") if user_row else None,
    )


async def get_optional_user(
    request: Request,
    authorization: Optional[str] = Security(API_HEADER),
    cookie: Optional[str] = Security(API_COOKIE),
) -> Optional[Identity]:
    try:
        identity = await get_user(request, authorization, cookie)
        return identity
    except HTTPException:
        return None


def require_route_access(
    category: RouteCategory, required_role: Optional[Role] = None
):
    async def _dependency(
        identity: Optional[Identity] = Depends(get_optional_user),
    ):
        # Service API key bypasses every check — its access is gated by holding
        # the key, not by holding a role.
        if identity and identity.type == "service_api_key":
            logger.debug(f"Service key access granted for category={category}")
            return identity

        # SERVICE category: only service_api_key allowed (handled above).
        if category == RouteCategory.SERVICE:
            logger.debug(
                f"Non-service identity denied for SERVICE category: {getattr(identity, 'email', None)}"
            )
            raise HTTPException(
                status_code=403, detail="User does not have access to this resource"
            )

        # Public
        if category == RouteCategory.PUBLIC:
            return identity

        # Authenticated — any signed-in identity.
        if category == RouteCategory.AUTHENTICATED:
            if identity is None:
                raise HTTPException(status_code=403, detail="Authentication required")
            return identity

        # Team-required (now: minimum trust level on the ladder).
        if category == RouteCategory.TEAM_REQUIRED:
            if identity is None:
                raise HTTPException(status_code=403, detail="Authentication required")
            if required_role is None:
                # No level specified — equivalent to AUTHENTICATED.
                return identity
            if not has_at_least(identity.role, required_role):
                logger.debug(
                    f"Trust ladder denied: user role={identity.role}, required >= {required_role}"
                )
                raise HTTPException(
                    status_code=403, detail="User does not have required trust level"
                )
            return identity

    return _dependency


async def get_ws_user(websocket: WebSocket) -> Optional[Identity]:
    token = websocket.cookies.get("token")
    if not token:
        return None
    session = await session_service.get_session(token)
    if not session:
        return None
    provider = session["provider"]
    provider_user_id = session["provider_user_id"]
    user_row = await database.get_user(provider, provider_user_id)
    role = (user_row.get("role") if user_row else None) or session.get("role") or Role.DEFAULT.value
    return Identity(
        type="cookie",
        provider=provider,
        provider_user_id=provider_user_id,
        email=session.get("email"),
        role=role,
    )


def expect_user(identity, expected_provider, expected_provider_user_id):
    if not identity:
        return False, "No identity provided"

    if identity.type == "service_api_key":
        return True, "Identity is a service API key, skipping provider checks"

    if identity.provider != expected_provider:
        return False, f"Expected provider {expected_provider}, got {identity.provider}"

    if identity.provider_user_id != expected_provider_user_id:
        return (
            False,
            f"Expected provider_user_id {expected_provider_user_id}, got {identity.provider_user_id}",
        )

    return True, "Identity matches expected provider and provider_user_id"
