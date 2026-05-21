from urllib.parse import unquote, urlparse

import database.users as database
import lib.auth_session as session_service
import lib.supabase_auth as supabase_auth_service
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from lib.auth import get_optional_user
from schemas.common import (
    Identity,
    RequestOtpRequest,
    VerifyOtpRequest,
)

from supabase import AsyncClient


def is_safe_redirect(url: str, allowed_hosts: list[str]) -> bool:
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
    if hostname in allowed_hosts:
        return True
    return any(
        pat.startswith("*.") and hostname.endswith("." + pat[2:])
        for pat in allowed_hosts
    )


def get_router(is_production: bool) -> APIRouter:
    if is_production:
        allowed_hosts = ["civicpatch.org", "*.civicpatch.org"]
    else:
        allowed_hosts = ["localhost"]

    router = APIRouter()

    @router.get("/logout", include_in_schema=False)
    async def logout(
        redirect: str = "/",
        user: Identity | None = Depends(get_optional_user),
    ):
        redirect_url = redirect if is_safe_redirect(redirect, allowed_hosts) else "/"
        response = RedirectResponse(url=redirect_url)
        await session_service.clear_session_cookies(
            response,
            provider=user.provider if user else None,
            provider_user_id=user.provider_user_id if user else None,
        )
        return response

    @router.post("/supabase/request-otp", include_in_schema=False)
    async def request_otp(
        body: RequestOtpRequest,
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_client),
    ):
        try:
            await client.auth.sign_in_with_otp(
                {"email": body.email, "options": {"should_create_user": True}}
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"data": {"sent": True}}

    @router.post("/supabase/verify-otp", include_in_schema=False)
    async def verify_otp(
        body: VerifyOtpRequest,
        client: AsyncClient = Depends(supabase_auth_service.get_supabase_client),
    ):
        try:
            auth_response = await client.auth.verify_otp(
                {"email": body.email, "token": body.code, "type": "email"}
            )
        except Exception as exc:
            raise HTTPException(status_code=401, detail=str(exc))

        if auth_response.user is None:
            raise HTTPException(status_code=401, detail="No user in verify response")

        identity = supabase_auth_service.to_supabase_user(auth_response.user)
        await database.upsert_user(
            identity.provider, identity.id, identity.email, identity.display_name
        )

        response = JSONResponse(content={"data": {"authenticated": True}})
        await session_service.create_session_cookies(response, identity, teams=[])
        return response

    return router
