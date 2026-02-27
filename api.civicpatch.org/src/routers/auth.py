import os
import datetime
import time
from typing import cast
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi_sso import GithubSSO
from services import github_service
import database
import secrets
from urllib.parse import urlparse
from jose import jwt

INSTANCE_URL = os.getenv("INSTANCE_URL", "https://api.civicpatch.local")
COOKIE_INSTANCE_URL = os.getenv("COOKIE_INSTANCE_URL", ".civicpatch.local")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_CALLBACK_URL = f"{INSTANCE_URL}/api/v1/auth/github/callback"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

ALLOWED_HOSTS = ["civicpatch.org", "civicpatch.local"]

def is_safe_redirect(url: str) -> bool:
    """Check if the redirect URL is safe (relative URL or allowed host)."""
    if not url:
        return False

    # Normalize URL to handle browser quirks:
    # - Replace backslashes, which some browsers treat like slashes.
    # - Strip surrounding whitespace.
    normalized_url = url.replace("\\", "/").strip()
    if not normalized_url:
        return False

    parsed = urlparse(normalized_url)

    # Allow only *relative* URLs with no scheme and no network location.
    # This prevents malformed absolute URLs like "https:/example.com"
    # from being treated as relative.
    if not parsed.scheme and not parsed.netloc:
        # Optionally, ensure the path starts with "/" to avoid confusing
        # relative values like "///example.com".
        if not parsed.path:
            return False
        if parsed.path.startswith("/"):
            return True
        # Paths that do not start with "/" can be considered unsafe here.
        return False

    # For absolute URLs, only allow specific hosts over HTTP(S).
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname or ""
    if not hostname:
        return False

    if hostname in ALLOWED_HOSTS:
        return True

    # Allow subdomains of civicpatch.org and civicpatch.local
    if hostname.endswith(".civicpatch.org") or hostname.endswith(".civicpatch.local"):
        return True

    return False

# https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
github_sso = GithubSSO(
    client_id=GITHUB_CLIENT_ID,
    client_secret=GITHUB_CLIENT_SECRET,
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
    async def logout(redirect: str = "/"):
        # TODO - connect this to redis (once we have it)
        # This would allow us to dynamically invalidate their sessions
        # based on team updates on GitHub
        """Forget the user's session."""
        
        # Validate the redirect URL
        redirect_url = redirect if is_safe_redirect(redirect) else "/"
        
        response = RedirectResponse(url=redirect_url)
        response.delete_cookie(
            key="token",
            domain=COOKIE_INSTANCE_URL,
            samesite="none",
            secure=True,  # required for samesite="none"
            path="/"
        )
        response.delete_cookie(
            key="csrf_token",
            domain=COOKIE_INSTANCE_URL,
            samesite="none",
            secure=True,
            path="/"
        ) 
        return response

    @router.get("/{provider}/callback", include_in_schema=False)
    async def login_callback(request: Request, provider: str, state: str = "/"):
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
        
        # Validate the redirect URL
        redirect_url = state if is_safe_redirect(state) else "/"
        
        # Create a JWT with the user's OpenID
        expiration = datetime.datetime.now(
            tz=datetime.timezone.utc
        ) + datetime.timedelta(days=1)

        teams = await github_service.get_teams(sso.access_token)

        await database.create_update_user(openid.provider, openid.id, openid.email, teams)
        # user = await database.get_user(openid.provider, openid.id)
        token = jwt.encode(
            {
                "pld": openid.model_dump(), 
                "exp": expiration,
                "sub": openid.id,
                "teams": teams
                #"roles": user.get("roles") if user else None
            },
            key=cast(str, JWT_SECRET_KEY),
            algorithm="HS256",
        )
        response = RedirectResponse(url=redirect_url, status_code=302)
        response.set_cookie(
            key="token",
            value=token,
            expires=expiration,
            httponly=True,
            secure=True,
            samesite="lax",
            domain=COOKIE_INSTANCE_URL,
            path="/"
        )
        # Create a signed CSRF token (stateless) and set it as a readable cookie
        csrf_payload = {"sub": openid.id, "iat": int(time.time()), "nonce": secrets.token_urlsafe(8)}
        csrf_signed = jwt.encode(csrf_payload, key=cast(str, JWT_SECRET_KEY), algorithm="HS256")

        response.set_cookie(
            key="csrf_token",
            value=csrf_signed,
            expires=expiration,
            httponly=False, # Allow JS to read the CSRF token
            secure=True,
            samesite="lax",
            domain=COOKIE_INSTANCE_URL,
            path="/"
        )
        return response

    return router