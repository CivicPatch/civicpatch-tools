import os
import datetime
import time
from typing import cast, Optional
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi_sso import GithubSSO
from services import github_service, session_service
from utils.auth_utils import get_optional_user
from schemas.common import Identity
import database
from urllib.parse import urlparse, unquote

INSTANCE_URL = os.getenv("INSTANCE_URL", "http://127.0.0.1:8000")
GITHUB_APP_CLIENT_ID = os.getenv("GITHUB_APP_CLIENT_ID")
GITHUB_APP_CLIENT_SECRET = os.getenv("GITHUB_APP_CLIENT_SECRET")
GITHUB_CALLBACK_URL = f"{INSTANCE_URL}/api/v1/auth/github/callback"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

APP_ENVIRONMENT = os.getenv("APP_ENVIRONMENT")
is_production = APP_ENVIRONMENT.lower() == "production"

if is_production:
    ALLOWED_HOSTS = [
        "civicpatch.org",
        "test.civicpatch.org",
        "test-api.civicpatch.org"
    ]
    COOKIE_INSTANCE_URL = os.getenv("COOKIE_INSTANCE_URL", ".civicpatch.org")
else:
    ALLOWED_HOSTS = ["localhost"]


def is_safe_redirect(url: str) -> bool:
    """Check if the redirect URL is safe (relative URL or allowed host)."""
    if not url or "\x00" in url:
        return False

    # Normalize: browsers treat backslashes as slashes; decode percent-encoding
    # before parsing so that %2F%2Fevil.com doesn't slip through.
    normalized = unquote(url.replace("\\", "/").strip())
    if not normalized:
        return False

    parsed = urlparse(normalized)

    # Relative URL: no scheme, no netloc.
    # Must start with "/" to block values like "javascript:..." that
    # urlparse may leave in `path`, and to ensure browser interpretation
    # as an absolute path on the current host.
    if not parsed.scheme and not parsed.netloc:
        return bool(parsed.path) and parsed.path.startswith("/")

    # Absolute URL: restrict to HTTP(S) on explicitly allowed hosts.
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname or ""
    # Use parsed.netloc-aware port check to avoid example.com:evil matching.
    return hostname in ALLOWED_HOSTS

# https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
github_sso = GithubSSO(
    client_id=GITHUB_APP_CLIENT_ID,
    client_secret=GITHUB_APP_CLIENT_SECRET,
    redirect_uri=GITHUB_CALLBACK_URL,
    scope=["read:user", "user:email", "read:org"]  # Requesting access to read user info and org membership
)

def get_router(is_production: bool) -> APIRouter:
    router = APIRouter()
 
    @router.get("/{provider}/login", include_in_schema=False)
    async def login(provider: str, request: Request, redirect: str = "/"):
        match provider:
            case "github":
                sso = github_sso
            case _:
                raise HTTPException(
                    status_code=400, detail=f"Unsupported provider: {provider}"
                )

        if is_safe_redirect(redirect):
            redirect_url = redirect
        else:
            redirect_url = "/"

        # Store redirect in session or pass via state parameter
        async with sso:
            # Pass redirect URL via OAuth state parameter
            return await sso.get_login_redirect(state=redirect_url)

    @router.get("/logout", include_in_schema=False)
    async def logout(
        redirect: str = "/",
        user: Optional[Identity] = Depends(get_optional_user),
    ):
        redirect_url = redirect if is_safe_redirect(redirect) else "/"
        response = RedirectResponse(url=redirect_url)
        session_service.clear_session_cookies(
            response,
            provider=user.provider if user else None,
            provider_user_id=user.provider_user_id if user else None,
        )
        return response

    @router.get("/{provider}/callback", include_in_schema=False)
    async def login_callback(request: Request, provider: str, state: str = "/"):
        match provider:
            case "github":
                sso = github_sso
            case _:
                raise HTTPException(status_code=400, detail="Unsupported provider")

        async with sso:
            openid = await sso.verify_and_process(request)
            if not openid:
                raise HTTPException(status_code=401, detail="Authentication failed")
            access_token = sso.access_token

        redirect_url = state if is_safe_redirect(state) else "/"
        teams = await github_service.get_teams(access_token)
        await database.create_update_user(openid.provider, openid.id, openid.email, teams)

        response = RedirectResponse(url=redirect_url, status_code=302)
        session_service.create_session_cookies(response, openid, teams)
        return response

    return router