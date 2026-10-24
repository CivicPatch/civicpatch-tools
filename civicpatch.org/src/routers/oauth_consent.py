"""The consent page Supabase's OAuth server sends a signing-in MCP client's user to; our own cookie says who they are."""

from typing import Annotated, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

import environment
import services.connected_apps as service
from lib.auth import get_optional_person, require_route_access
from lib.auth_session import CSRF_COOKIE
from lib.supabase_oauth import APPROVE, DENY, SupabaseAuthError
from routers.frontend import get_page_user
from schemas.common import Identity, RouteCategory, UserRole, has_at_least

CONSENT_PATH = "/oauth/consent"
CONSENT_TEMPLATE = "pages/oauth-consent.html"
# Supabase's ids are opaque strings; this keeps one safe to put into its API path and our HTML.
AUTHORIZATION_ID = r"^[A-Za-z0-9_-]{1,128}$"
NOT_A_MAINTAINER = "Only maintainers can connect an app to civicpatch."
REQUEST_UNUSABLE = "This request has expired or is not valid. Start again from the app."


def _client_name(authorization: dict) -> str:
    client = authorization.get("client") or {}
    return client.get("name") or client.get("client_name") or client.get("id") or "An app"


def _login_url(authorization_id: str) -> str:
    return f"/login?{urlencode({'next': f'{CONSENT_PATH}?authorization_id={authorization_id}'})}"


def get_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    def message_page(request: Request, user: dict, message: str):
        return templates.TemplateResponse(CONSENT_TEMPLATE, {"request": request, "user": user, "message": message})

    @router.get(CONSENT_PATH, include_in_schema=False)
    async def consent_page(
        request: Request,
        authorization_id: Annotated[str, Query(pattern=AUTHORIZATION_ID)],
        _: Optional[Identity] = Depends(require_route_access(RouteCategory.PUBLIC)),
        identity: Optional[Identity] = Depends(get_optional_person),
        user: dict = Depends(get_page_user),
    ):
        if identity is None:
            return RedirectResponse(_login_url(authorization_id), status_code=303)
        if not has_at_least(identity.role, UserRole.MAINTAINERS):
            return message_page(request, user, NOT_A_MAINTAINER)
        try:
            url, key = environment.supabase_url_and_secret_key()
            authorization = await service.fetch_authorization_request(url, key, identity.provider_user_id, authorization_id)
        except SupabaseAuthError:
            return message_page(request, user, REQUEST_UNUSABLE)
        already_approved = authorization.get("redirect_url") or authorization.get("redirect_to")
        if already_approved:
            return RedirectResponse(already_approved, status_code=303)
        return templates.TemplateResponse(CONSENT_TEMPLATE, {
            "request": request,
            "user": user,
            "client_name": _client_name(authorization),
            "authorization_id": authorization_id,
            "csrf_token": request.cookies.get(CSRF_COOKIE, ""),
            "consent_path": CONSENT_PATH,
            "approve": APPROVE,
            "deny": DENY,
        })

    @router.post(CONSENT_PATH, include_in_schema=False)
    async def consent_decide(
        request: Request,
        authorization_id: Annotated[str, Form(pattern=AUTHORIZATION_ID)],
        action: Annotated[str, Form(pattern=f"^({APPROVE}|{DENY})$")],
        identity: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
        user: dict = Depends(get_page_user),
    ):
        try:
            url, key = environment.supabase_url_and_secret_key()
            redirect_url = await service.decide_authorization_request(url, key, identity.provider_user_id, authorization_id, action)
        except SupabaseAuthError:
            return message_page(request, user, REQUEST_UNUSABLE)
        return RedirectResponse(redirect_url, status_code=303)

    return router
