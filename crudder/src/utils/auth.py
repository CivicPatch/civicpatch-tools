import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyCookie
from fastapi_sso.sso.base import OpenID
from jose import jwt
from typing import cast

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

async def get_logged_user(
    cookie: str = Security(APIKeyCookie(name="token"))
) -> OpenID:
    """Get user's JWT stored in cookie 'token', parse it and return the user's OpenID."""
    try:
        claims = jwt.decode(cookie, key=cast(str, JWT_SECRET_KEY), algorithms=["HS256"])
        return OpenID(**claims["pld"])
    except Exception as error:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        ) from error
