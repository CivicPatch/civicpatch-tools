import logging
import os
import time
from typing import List, Optional, cast

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyCookie, APIKeyHeader
from fastapi_sso.sso.base import OpenID
from jose import JWTError, jwt

import database.database as database
from schemas.common import Identity, Role, RouteCategory
from services import session_service

logger = logging.getLogger(__name__)

import environment

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

    # 3. Handle service API key
    if token_source == "service_api_key":
        return Identity(
            type="service_api_key",
            provider="system",
            provider_user_id="service_api_key",
            email="service@civicpatch.org",
            teams=[Role.CONTRIBUTORS, Role.MAINTAINERS, Role.ADMINS],
        )

    try:
        if token_source == "cookie":
            identity = await get_user_by_cookie(request, token)
        elif token_source == "header":
            identity = await get_user_by_api_key(token)
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
        provider=user.get("provider"),
        provider_user_id=user.get("provider_user_id"),
        email=user.get("email"),
        teams=user.get("teams", []),  # <-- pass list of teams
    )


# Update Identity creation to use teams (list)
async def get_user_by_cookie(request, token: str) -> Identity:
    env = environment.get_env_vars()
    JWT_SECRET_KEY = env["JWT_SECRET_KEY"]
    JWT_AUDIENCE = env.get("JWT_AUDIENCE")
    JWT_ISSUER = env.get("JWT_ISSUER")

    try:
        decode_kwargs = {"key": cast(str, JWT_SECRET_KEY), "algorithms": ["HS256"]}
        if JWT_AUDIENCE:
            decode_kwargs["audience"] = JWT_AUDIENCE
        if JWT_ISSUER:
            decode_kwargs["issuer"] = JWT_ISSUER
        claims = jwt.decode(token, **decode_kwargs)
        payload = claims.get("pld", claims)
    except JWTError as e:
        print(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )

    print("checking for session...")
    # Check if session was invalidated (e.g., logout)
    provider = payload.get("provider")
    provider_user_id = str(claims.get("sub", ""))
    if provider and provider_user_id:
        stored = await session_service.get_session(provider, provider_user_id)
        if stored is None:
            raise HTTPException(
                status_code=401, detail="Session expired or invalidated"
            )
    print(f"session check passed")
    # CSRF protection for cookie-authenticated unsafe requests
    if request.method.upper() in UNSAFE_METHODS:
        csrf_token = request.headers.get("x-csrf-token")
        print(
            f"CSRF check: method={request.method}, has_csrf_header={csrf_token is not None}"
        )
        if not csrf_token:
            form = await request.form()
            csrf_token = form.get("csrf_token")
            print(
                f"CSRF check: fell back to form field, has_csrf_form={csrf_token is not None}"
            )

        csrf_cookie = request.cookies.get("csrf_token")
        print(
            f"CSRF check: has_csrf_cookie={csrf_cookie is not None}, tokens_match={csrf_token == csrf_cookie if csrf_token and csrf_cookie else False}"
        )
        if not csrf_token or not csrf_cookie or csrf_token != csrf_cookie:
            print(
                f"CSRF double-submit failed: csrf_token={bool(csrf_token)}, csrf_cookie={bool(csrf_cookie)}"
            )
            raise HTTPException(
                status_code=403,
                detail="CSRF check failed for cookie-authenticated request",
            )

        try:
            decoded_csrf = jwt.decode(
                csrf_cookie, key=cast(str, JWT_SECRET_KEY), algorithms=["HS256"]
            )
            print(
                f"CSRF JWT decoded successfully: sub={decoded_csrf.get('sub')}, iat={decoded_csrf.get('iat')}"
            )
        except JWTError as e:
            print(f"CSRF JWT decode failed: {e}")
            raise HTTPException(status_code=403, detail="Invalid CSRF token")

        csrf_sub = decoded_csrf.get("sub")
        auth_sub = claims.get("sub")
        if not csrf_sub or not auth_sub or str(csrf_sub) != str(auth_sub):
            print(f"CSRF subject mismatch: csrf_sub={csrf_sub}, auth_sub={auth_sub}")
            raise HTTPException(status_code=403, detail="CSRF token subject mismatch")

        iat = decoded_csrf.get("iat")
        now = int(time.time())
        if not iat or (now - int(iat) > 24 * 3600):
            print(
                f"CSRF token expired: iat={iat}, now={now}, age={now - int(iat) if iat else 'N/A'}s"
            )
            raise HTTPException(status_code=403, detail="Expired CSRF token")

        print("CSRF validation passed")

    openid_obj = OpenID(**payload)
    teams = payload.get("teams")  # <-- expect a list from token payload

    if not teams:
        provider = payload.get("provider") or getattr(openid_obj, "provider", None)
        provider_user_id = (
            payload.get("sub") or payload.get("id") or getattr(openid_obj, "id", None)
        )
        if provider and provider_user_id:
            user_row = await database.get_user(provider, provider_user_id)
            if user_row and user_row.get("teams"):
                teams = user_row["teams"]

    return Identity(
        type="cookie",
        provider=openid_obj.provider,
        provider_user_id=openid_obj.id,
        email=openid_obj.email,
        teams=teams or [],
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
    category: RouteCategory, teams_required: Optional[List[str]] = None
):
    async def _dependency(
        identity: Identity = Depends(get_optional_user),
    ):
        # Service API key always allowed for SERVICE routes, and optionally for others
        if identity and identity.type == "service_api_key":
            print(f"Service key access granted for category={category}")
            return identity

        # Explicitly deny non-service identities for SERVICE category
        if category == RouteCategory.SERVICE:
            print(
                f"Non-service identity denied for SERVICE category: {getattr(identity, 'email', None)}"
            )
            raise HTTPException(
                status_code=403, detail="User does not have access to this resource"
            )

        # Public
        if category == RouteCategory.PUBLIC:
            return identity

        # Authenticated
        if category == RouteCategory.AUTHENTICATED and identity is not None:
            print(
                f"Authenticated access granted for category={category}, email={identity.email}"
            )
            return identity

        # Team required
        user_teams = identity.teams if identity else []
        user_teams = [] if not user_teams else user_teams
        print(f"user_teams={user_teams}")

        if category == RouteCategory.TEAM_REQUIRED and len(user_teams) == 0:
            print(
                f"Team required access denied for category={category}, user email={getattr(identity, 'email', None)}, no teams found, but at least one team is required"
            )
            raise HTTPException(
                status_code=403,
                detail="User does not have required team membership on team required route",
            )

        if (
            user_teams
            and teams_required
            and not any(team in user_teams for team in teams_required)
        ):
            print(
                f"Team required access denied for category={category}, user email={identity.email}, user teams={user_teams}, required teams={teams_required}"
            )
            raise HTTPException(
                status_code=403, detail="User does not have required team membership"
            )

        if (
            user_teams
            and teams_required
            and any(team in user_teams for team in teams_required)
        ):
            print(
                f"Team required access granted for category={category}, user email={identity.email}, user teams={user_teams}, required teams={teams_required}"
            )
            return identity

        # Unknown category fallback
        print(
            f"Unknown route: Access denied for category={category}, user email={getattr(identity, 'email', None)}, teams={getattr(identity, 'teams', None)}"
        )
        raise HTTPException(
            status_code=403, detail="User does not have access to this resource"
        )

    return _dependency


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
