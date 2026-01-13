from typing import Optional, List
import os
from fastapi import HTTPException, Security, Header, Request, Depends, Cookie
from fastapi.security import APIKeyCookie, APIKeyHeader
from fastapi_sso.sso.base import OpenID
from jose import jwt, JWTError
import time
from typing import cast, Annotated
import database
from http import cookies as _cookies
from schemas import Identity, RouteCategory, UserRole, ApiKeyType

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
API_COOKIE = APIKeyCookie(name="token", auto_error=False)
API_HEADER = APIKeyHeader(name="Authorization", auto_error=False)

JWT_AUDIENCE = os.getenv("JWT_AUDIENCE")
JWT_ISSUER = os.getenv("JWT_ISSUER")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Define ROUTE_PERMISSIONS once at module level
ROUTE_PERMISSIONS = {
    RouteCategory.COMPONENT_API: {
        UserRole.ADMIN: [ApiKeyType.SERVER_KEY, ApiKeyType.INTERNAL_SERVER_KEY],
        UserRole.MEMBER: [ApiKeyType.SERVER_KEY, ApiKeyType.INTERNAL_SERVER_KEY], 
        UserRole.UNVERIFIED: [ApiKeyType.SERVER_KEY, ApiKeyType.INTERNAL_SERVER_KEY]
    },
    RouteCategory.ADMIN_ONLY: {
        UserRole.ADMIN: [ApiKeyType.SERVER_KEY]
    },
    RouteCategory.INTERNAL_API: {
        UserRole.ADMIN: [ApiKeyType.SERVER_KEY, ApiKeyType.INTERNAL_SERVER_KEY],
        UserRole.MEMBER: [ApiKeyType.SERVER_KEY, ApiKeyType.INTERNAL_SERVER_KEY],
        UserRole.UNVERIFIED: [ApiKeyType.SERVER_KEY, ApiKeyType.INTERNAL_SERVER_KEY]
    },
    RouteCategory.JOBS_API: {
        #UserRole.ADMIN: [ApiKeyType.SERVER_KEY],
        UserRole.JOBS: [ApiKeyType.SERVER_KEY]
    }
}

async def get_user(
    request: Request,
    authorization: Optional[str] = Security(API_HEADER),
    cookie: Optional[str] = Security(API_COOKIE),
) -> Identity:
    """Authenticate from Authorization: Bearer <token> or from cookie 'token'.
    Enforce simple CSRF check for unsafe cookie-authenticated requests.
    """
    token = None
    token_source = None
    if authorization:
        token = authorization.strip()
        token_source = "header"
    elif cookie:
        token = cookie
        token_source = "cookie"

    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

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

# Update Identity creation to use roles (list)
async def get_user_by_api_key(api_key: str) -> Identity:
    user = await database.get_user_by_api_key(api_key)

    if not user:
        raise HTTPException(status_code=401, detail="No identity found using api key")

    return Identity(
        provider=user.get("provider"),
        provider_user_id=user.get("provider_user_id"),
        email=user.get("email"),
        roles=user.get("roles", [])  # <-- pass list of roles
    )

# Update Identity creation to use roles (list)
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
    roles = payload.get("roles")  # <-- expect a list from token payload

    if not roles:
        provider = payload.get("provider") or getattr(openid_obj, "provider", None)
        provider_user_id = payload.get("sub") or payload.get("id") or getattr(openid_obj, "id", None)
        if provider and provider_user_id:
            user_row = await database.get_user(provider, provider_user_id)
            if user_row and user_row.get("roles"):
                roles = user_row["roles"]

    return Identity(
        provider=openid_obj.provider,
        provider_user_id=openid_obj.id,
        email=openid_obj.email,
        roles=roles or []
    )

async def get_optional_user(
    request: Request,
    authorization: Optional[str] = Security(API_HEADER),
    cookie: Optional[str] = Security(API_COOKIE),
    #csrf_token: Optional[str] = Header(None, alias="x-csrf-token"),
    #csrf_cookie: Optional[str] = Cookie(None, alias="csrf_token"),
 ) -> Optional[Identity]:
    try:
        identity = await get_user(request, authorization, cookie)
        return identity
    except HTTPException:
        return None


def require_any_role(*allowed_roles: str):
    """
    Factory that returns a dependency callable. Use in routes as:
      current_user = Depends(require_role("admin"))
    or router dependencies: dependencies=[Depends(require_role("member","admin"))]
    """
    async def _dependency(user: Identity = Depends(get_user)):
        user_roles = getattr(user, "roles", [])
        if allowed_roles:
            if not any(role in allowed_roles for role in user_roles):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _dependency

def get_api_key_type(
    authorization: Optional[str] = Security(API_HEADER),
    cookie: Optional[str] = Security(API_COOKIE),
):
    """Determine the API key type used for authentication."""
    token = None
    if authorization:
        token = authorization.strip()
        if token.startswith("pk_"):
            return ApiKeyType.WIDGET_KEY  # Widget/component key
        else:
            return ApiKeyType.SERVER_KEY  # General server key
    elif cookie:
        token = cookie
        return ApiKeyType.INTERNAL_SERVER_KEY # Server generated key

    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    

def get_api_key_type_from_auth(
    authorization: Optional[str] = None,
    cookie: Optional[str] = None
) -> Optional[ApiKeyType]:
    """Helper to determine API key type from auth sources"""
    if authorization:
        if authorization.strip().startswith("pk_"):
            return ApiKeyType.WIDGET_KEY
        else:
            return ApiKeyType.SERVER_KEY
    elif cookie:
        return ApiKeyType.INTERNAL_SERVER_KEY
    return None

def require_route_access(category: RouteCategory):
    """Factory that returns a dependency for route category access control"""
    async def _dependency(user: Identity = Depends(get_user), api_key_type: ApiKeyType = Depends(get_api_key_type)):
        user_roles = getattr(user, "roles", [])
        allowed_key_types = []
        for role in user_roles:
            allowed_key_types.extend(ROUTE_PERMISSIONS.get(category, {}).get(role, []))
        if api_key_type not in allowed_key_types:
            raise HTTPException(status_code=403, detail="Insufficient permissions for this route")
        return user
    return _dependency

def require_route_access_optional(category: RouteCategory):
    """Factory that returns an optional dependency for route category access control"""
    async def _dependency(
        request: Request,
        authorization: Optional[str] = Security(API_HEADER),
        cookie: Optional[str] = Security(API_COOKIE)
    ):
        # If no auth headers provided, allow anonymous access
        if not authorization and not cookie:
            return None
            
        # If auth headers are provided, validate them properly
        try:
            user = await get_user(request, authorization, cookie)
        except HTTPException:
            raise
            
        # If auth is valid, enforce permissions
        api_key_type = get_api_key_type_from_auth(authorization, cookie)
        if not api_key_type:
            return user  # Shouldn't happen if user exists, but handle gracefully

        roles = user.roles
        allowed_key_types = set()
        for role in roles:
            allowed_key_types.update(ROUTE_PERMISSIONS.get(category, {}).get(role, []))

        if api_key_type not in allowed_key_types:
            raise HTTPException(
                status_code=403, 
                detail=f"Insufficient permissions for this route. Roles {roles} cannot use {api_key_type} for {category}"
            )
        
        return user

    return _dependency