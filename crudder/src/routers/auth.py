import datetime
import os

import jwt
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_sso import GithubSSO

import database

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_CALLBACK_URL = os.getenv("GITHUB_CALLBACK_URL")

github_sso = GithubSSO(
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
    redirect_uri=GITHUB_CALLBACK_URL,
)


def get_router(is_production: bool) -> APIRouter:
    router = APIRouter()

    @router.get("/{provider}/login", include_in_schema=False)
    async def login(provider: str):
        match provider:
            case "github":
                sso = github_sso
            case _:
                raise HTTPException(
                    status_code=400, detail="Unsupported provider: {provider}"
                )

        async with sso:
            return await sso.get_login_redirect()

    @router.get("/logout", include_in_schema=False)
    async def logout():
        """Forget the user's session."""
        response = RedirectResponse(url="/")
        response.delete_cookie(key="token")
        return response

    @router.get("/{provider}/callback", include_in_schema=False)
    async def login_callback(request: Request, provider: str):
        match provider:
            case "github":
                sso = github_sso
            case _:
                raise HTTPException(status_code=400, detail="Unsupported provider")

        """Process login and redirect the user to the protected endpoint."""
        async with sso:
            openid = await sso.verify_and_process(request)
            if not openid:
                raise HTTPException(status_code=401, detail="Authentication failed")
        # Create a JWT with the user's OpenID
        expiration = datetime.datetime.now(
            tz=datetime.timezone.utc
        ) + datetime.timedelta(days=1)
        token = jwt.encode(
            {"pld": openid.model_dump(), "exp": expiration, "sub": openid.id},
            key=JWT_SECRET_KEY,
            algorithm="HS256",
        )
        await database.maybe_insert_user(openid.provider, openid.id, openid.email)

        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(
            key="token",
            value=token,
            expires=expiration,
            httponly=True,
            secure=is_production,
            samesite="lax",
        )
        return response

    return router
