from typing import Optional, List
import os
from fastapi import HTTPException, Security, Request, Depends
from fastapi.security import APIKeyCookie, APIKeyHeader
from fastapi_sso.sso.base import OpenID
from jose import jwt, JWTError
import time
from typing import cast
import database
from schemas.common import Identity, RouteCategory, ROUTE_PERMISSIONS

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
API_COOKIE = APIKeyCookie(name="token", auto_error=False)
API_HEADER = APIKeyHeader(name="Authorization", auto_error=False)

JWT_AUDIENCE = os.getenv("JWT_AUDIENCE")
JWT_ISSUER = os.getenv("JWT_ISSUER")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

async def get_user(
    request: Request,
    authorization: Optional[str] = Security(API_HEADER),
    cookie: Optional[str] = Security(API_COOKIE),
) -> Identity:
    service_api_key = os.getenv("SERVICE_API_KEY")
    auth_header = request.headers.get("authorization")

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
            type="service_key",
            provider="system",
            provider_user_id="service_api_key",
            email=None,
            teams=[]
        )

    if not JWT_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Server not configured to verify tokens")
    
    try:
        if token_source == "cookie":
            identity = await get_user_by_cookie(request, token)
        elif token_source == "header":
            identity = await get_user_by_api_key(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Failed to construct identity object: {e}")

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
        teams=user.get("teams", [])  # <-- pass list of teams
    )

# Update Identity creation to use teams (list)
async def get_user_by_cookie(request, token: str) -> Identity:
    try: #TODO
        decode_kwargs = {"key": cast(str, JWT_SECRET_KEY), "algorithms": ["HS256"]}
        if JWT_AUDIENCE:
            decode_kwargs["audience"] = JWT_AUDIENCE
        if JWT_ISSUER:
            decode_kwargs["issuer"] = JWT_ISSUER
        claims = jwt.decode(token, **decode_kwargs)
        payload = claims.get("pld", claims)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    # CSRF protection for cookie-authenticated unsafe requests
    if request.method.upper() in UNSAFE_METHODS:
        # Prefer header (AJAX), fall back to form field for plain HTML forms
        csrf_token = request.headers.get("x-csrf-token")
        if not csrf_token:
            form = await request.form()
            csrf_token = form.get("csrf_token")

        csrf_cookie = request.cookies.get("csrf_token")
        # Require double-submit: submitted token must equal cookie
        if not csrf_token or not csrf_cookie or csrf_token != csrf_cookie:
            raise HTTPException(status_code=403, detail="CSRF check failed for cookie-authenticated request")

        # Verify signed csrf cookie integrity and freshness
        try:
            decoded_csrf = jwt.decode(
                csrf_cookie, key=cast(str, JWT_SECRET_KEY), algorithms=["HS256"]
            )
        except JWTError:
            raise HTTPException(status_code=403, detail="Invalid CSRF token")

        # check token subject matches authenticated subject (claims['sub'])
        csrf_sub = decoded_csrf.get("sub")
        auth_sub = claims.get("sub")
        if not csrf_sub or not auth_sub or str(csrf_sub) != str(auth_sub):
            raise HTTPException(status_code=403, detail="CSRF token subject mismatch")

        # optional freshness: require issued within last 24 hours
        iat = decoded_csrf.get("iat")
        if not iat or (int(time.time()) - int(iat) > 24 * 3600):
            raise HTTPException(status_code=403, detail="Expired CSRF token")

    openid_obj = OpenID(**payload)
    teams = payload.get("teams")  # <-- expect a list from token payload

    if not teams:
        provider = payload.get("provider") or getattr(openid_obj, "provider", None)
        provider_user_id = payload.get("sub") or payload.get("id") or getattr(openid_obj, "id", None)
        if provider and provider_user_id:
            user_row = await database.get_user(provider, provider_user_id)
            if user_row and user_row.get("teams"):
                teams = user_row["teams"]

    return Identity(
        type="cookie",
        provider=openid_obj.provider,
        provider_user_id=openid_obj.id,
        email=openid_obj.email,
        teams=teams or []
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

def require_route_access(category: RouteCategory):
    async def _dependency(
        identity: Identity = Depends(get_user),
    ):
        permission = ROUTE_PERMISSIONS.get(category)
        if not permission:
            raise HTTPException(status_code=403, detail="Unknown route category.")

        # Public
        if permission.public:
            return identity

        # Service key — not tied to a person, skip all team checks
        if permission.allow_service_key and identity.type == "service_key":
            return identity

        # Session-only routes — reject non-session auth
        if permission.allow_session and identity.type != "service_key":
            if identity.type != "session" and not permission.allow_user_key:
                raise HTTPException(status_code=403, detail="This route requires a user session.")

            # User API key or session — resolve teams from DB if needed
            user_teams = identity.teams

            if permission.required_teams and not any(t in permission.required_teams for t in user_teams):
                raise HTTPException(status_code=403, detail="Insufficient team permissions.")

            return identity

        raise HTTPException(status_code=403, detail="Access denied.")

    return _dependency