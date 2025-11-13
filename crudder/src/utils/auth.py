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
from schemas import Identity

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

async def get_user_by_api_key(api_key: str) -> Identity:
    user = await database.get_user_by_api_key(api_key)

    if not user:
        raise HTTPException(status_code=401, detail="No identity found using api key")

    return Identity(
        provider=user.get("provider"),
        provider_user_id=user.get("provider_user_id"),
        email=user.get("email"),
        role=user.get("role")
    )

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
        print("found csrf token", csrf_token)
        if not csrf_token:
            form = await request.form()
            print("founda form")
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
    role = payload.get("role")  # <- read role directly from the token's payload first

    if not role:
        provider = payload.get("provider") or getattr(openid_obj, "provider", None)
        provider_user_id = payload.get("sub") or payload.get("id") or getattr(openid_obj, "id", None)
        if provider and provider_user_id:
            user_row = await database.get_user(provider, provider_user_id)
            if user_row and user_row.get("role"):
                role = user_row["role"]

    return Identity(
        provider=openid_obj.provider,
        provider_user_id=openid_obj.id,
        email=openid_obj.email,
        role=role
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


def require_role(*allowed_roles: str):
    """
    Factory that returns a dependency callable. Use in routes as:
      current_user = Depends(require_role("admin"))
    or router dependencies: dependencies=[Depends(require_role("member","admin"))]
    """
    async def _dependency(user: Identity = Depends(get_user)):
        # read roles from Identity object
        try:
            role = user.role
        except Exception:
            role = getattr(user, "role", None)

        if allowed_roles:
            print("current role", role)
            print("allowed_roles", allowed_roles)
            if role not in allowed_roles:
                raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return _dependency
