import json
import os
from typing import cast, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database.jurisdictions import get_jurisdiction
from database.users import get_user_by_username
from shared.utils.id_utils import OCDID_PREFIX, folder_to_jurisdiction_ocdid

from schemas.common import Identity, UserRole, has_at_least
from lib.auth import get_optional_user
from lib.blog import get_all_posts, get_post

_is_production = os.getenv("APP_ENVIRONMENT", "").lower() == "production"




def _path_to_jurisdiction_ocdid(path: str) -> str:
    """A jurisdiction page's URL is its ocdid. The old `{state}/local/{place}` folder form still
    resolves, so links published before the switch keep working.

    Checked by prefix rather than by letting the folder parser fail: it reads segments 0 and 2
    and only rejects `len < 3`, so relying on it to reject is relying on luck.
    """
    if path.startswith(f"{OCDID_PREFIX}/"):
        return path
    return folder_to_jurisdiction_ocdid(path)

def _build_user_dict(identity: Optional[Identity]) -> dict:
    if not identity:
        return {"authenticated": False, "email": None, "permissions": build_permissions(None)}
    return {
        "authenticated": True,
        "email": identity.email,
        "user_id": identity.user_id,
        "role": identity.role,
        "permissions": build_permissions(identity),
        "username": identity.username,
        "avatar_url": None,
    }


def needs_username(user: dict) -> bool:
    # A freshly created account's username is its own id (see `database.users.create_user`) —
    # that equality is the signal that sign-up hasn't finished, gating every page until
    # `/login/username` clears it via `POST /api/v1/user/username`.
    return bool(user["authenticated"] and user["user_id"] and user["username"] == user["user_id"])


def build_permissions(identity: Optional[Identity]) -> dict:
    role = identity.role if identity else None
    return {
        "can_view_queue_page": has_at_least(role, UserRole.CONTRIBUTORS),
        # One key, because the caller no longer picks a mode: the environment does, server
        # side. Whether you may scrape is a role question; how it dispatches is not.
        "can_scrape": has_at_least(role, UserRole.MAINTAINERS),
        # The state-wide batch trigger, on the Pipelines page — separate from `can_scrape`
        # (a single jurisdiction, from its own page) because it moved to admins-only.
        "can_batch_scrape": has_at_least(role, UserRole.ADMINS),
        "can_view_reviews_page": has_at_least(role, UserRole.DEFAULT),
        "can_view_issues_page": has_at_least(role, UserRole.ADMINS),
        "can_view_activity_page": has_at_least(role, UserRole.DEFAULT),
        "can_edit_jurisdiction_data": has_at_least(role, UserRole.MAINTAINERS),
        "can_delete_directory_person": has_at_least(role, UserRole.CONTRIBUTORS),
        "can_reject_scrape": has_at_least(role, UserRole.CONTRIBUTORS),
        "can_cancel_pipeline_run": has_at_least(role, UserRole.ADMINS),
        # Same boundary as cancelling, but a separate key: reading why a run is stuck and
        # stopping it are different acts, and the frontend uses this one to decide whether to
        # poll at all rather than fire a rejected request every few seconds.
        "can_view_temporal_workflow_state": has_at_least(role, UserRole.ADMINS),
        # Money, all of it: what a scrape cost, the cadence driving it, and the caps it is
        # measured against. One boundary — seeing the spend without the ceiling is half an
        # answer. The rest of the Activity page stays signed-in.
        "can_edit_spend": has_at_least(role, UserRole.ADMINS),
        "can_write_config": has_at_least(role, UserRole.MAINTAINERS),
        "can_write_global_config": has_at_least(role, UserRole.ADMINS),
        "can_manage_roles": has_at_least(role, UserRole.ADMINS),
        # A design-review tool, not a data page — gated the same as the rest of the Admin
        # menu rather than opened up, so it stays a dev aid and not a second public surface.
        "can_view_gallery_page": has_at_least(role, UserRole.ADMINS),
    }


class PageRedirect(Exception):
    def __init__(self, location: str):
        self.location = location


async def _page_redirect_handler(request: Request, exc: Exception) -> RedirectResponse:
    return RedirectResponse(cast(PageRedirect, exc).location, status_code=303)


def register_page_redirects(app: FastAPI) -> None:
    app.add_exception_handler(PageRedirect, _page_redirect_handler)


async def get_page_user(identity: Optional[Identity] = Depends(get_optional_user)) -> dict:
    user = _build_user_dict(identity)
    if needs_username(user):
        raise PageRedirect("/login/username")
    return user


async def require_page_auth(user: dict = Depends(get_page_user)) -> dict:
    if not user["authenticated"]:
        raise PageRedirect("/")
    return user


def require_page_permission(permission_key: str):
    async def _dependency(user: dict = Depends(get_page_user)) -> dict:
        if not user["authenticated"] or not user["permissions"][permission_key]:
            raise PageRedirect("/")
        return user

    return _dependency


def get_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get("/api/permissions", include_in_schema=False)
    async def permissions(identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        return {
            "authenticated": user["authenticated"],
            "data": user,
        }

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request, user: dict = Depends(get_page_user)):
        return templates.TemplateResponse("pages/index.html", {"request": request, "user": user})

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login_page(request: Request, user: dict = Depends(get_page_user)):
        return templates.TemplateResponse(
            "pages/login.html",
            {
                "request": request,
                "user": user,
            },
        )

    @router.get("/login/username", response_class=HTMLResponse, include_in_schema=False)
    async def login_username_page(
        request: Request, identity: Optional[Identity] = Depends(get_optional_user)
    ):
        user = _build_user_dict(identity)
        if not user["authenticated"]:
            return RedirectResponse("/login", status_code=303)
        if not needs_username(user):
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse(
            "pages/login-username.html",
            {
                "request": request,
                "user": user,
            },
        )

    @router.get("/bulk-review", response_class=HTMLResponse, include_in_schema=False)
    async def bulk_review_page(
        request: Request, user: dict = Depends(require_page_permission("can_view_queue_page"))
    ):
        return templates.TemplateResponse("pages/bulk-review.html", {"request": request, "user": user})

    @router.get("/review", response_class=HTMLResponse, include_in_schema=False)
    async def review_page(
        request: Request, user: dict = Depends(require_page_permission("can_view_reviews_page"))
    ):
        return templates.TemplateResponse("pages/review.html", {"request": request, "user": user})

    @router.get("/review/session", response_class=HTMLResponse, include_in_schema=False)
    async def review_session_page(
        request: Request, user: dict = Depends(require_page_permission("can_view_reviews_page"))
    ):
        return templates.TemplateResponse("pages/review-session.html", {"request": request, "user": user})

    @router.get("/issues", response_class=HTMLResponse, include_in_schema=False)
    async def issues_page(
        request: Request, user: dict = Depends(require_page_permission("can_view_issues_page"))
    ):
        return templates.TemplateResponse("pages/issues.html", {"request": request, "user": user})

    @router.get("/spend", response_class=HTMLResponse, include_in_schema=False)
    async def spend_page(
        request: Request, user: dict = Depends(require_page_permission("can_edit_spend"))
    ):
        return templates.TemplateResponse("pages/spend.html", {"request": request, "user": user})

    @router.get("/pipelines", response_class=HTMLResponse, include_in_schema=False)
    async def pipelines_page(
        request: Request, user: dict = Depends(require_page_permission("can_batch_scrape"))
    ):
        return templates.TemplateResponse("pages/pipelines.html", {"request": request, "user": user})

    @router.get("/gallery", response_class=HTMLResponse, include_in_schema=False)
    async def gallery_page(
        request: Request, user: dict = Depends(require_page_permission("can_view_gallery_page"))
    ):
        return templates.TemplateResponse("pages/gallery.html", {"request": request, "user": user})

    # `/activity` is a section, not a page: the change log and the cross-state changeset
    # summary are two views of "what has been happening". The bare path redirects rather than
    # 404ing, because it was the change log's own URL until this split.
    @router.get("/activity", response_class=HTMLResponse, include_in_schema=False)
    async def activity_index(request: Request):
        return RedirectResponse("/activity/all-activity", status_code=303)

    @router.get("/activity/all-activity", response_class=HTMLResponse, include_in_schema=False)
    async def activity_page(
        request: Request, user: dict = Depends(require_page_permission("can_view_activity_page"))
    ):
        return templates.TemplateResponse("pages/activity.html", {"request": request, "user": user})

    @router.get("/roles", response_class=HTMLResponse, include_in_schema=False)
    async def roles_page(
        request: Request, user: dict = Depends(require_page_permission("can_write_config"))
    ):
        return templates.TemplateResponse("pages/roles.html", {"request": request, "user": user})

    @router.get("/imports", response_class=HTMLResponse, include_in_schema=False)
    async def imports_page(
        request: Request, user: dict = Depends(require_page_permission("can_write_config"))
    ):
        return templates.TemplateResponse("pages/imports.html", {"request": request, "user": user})

    @router.get("/activity/calendar", response_class=HTMLResponse, include_in_schema=False)
    async def changesets_page(
        request: Request, user: dict = Depends(require_page_permission("can_view_activity_page"))
    ):
        # Same gate as the change log beside it — the section is one thing. The scrape control
        # this page carries is gated separately, on `can_scrape`.
        return templates.TemplateResponse("pages/changesets.html", {"request": request, "user": user})

    @router.get("/admin/users", response_class=HTMLResponse, include_in_schema=False)
    async def admin_page(
        request: Request, user: dict = Depends(require_page_permission("can_manage_roles"))
    ):
        return templates.TemplateResponse("pages/admin.html", {"request": request, "user": user})

    @router.get("/~{username}", response_class=HTMLResponse, include_in_schema=False)
    async def user_profile_page(
        request: Request,
        username: str,
        # Same gate as `/admin/users`: this is a moderation view of someone else's account, not a
        # self-service profile.
        user: dict = Depends(require_page_permission("can_manage_roles")),
    ):
        target_user = await get_user_by_username(username)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        return templates.TemplateResponse(
            "pages/user-profile.html",
            {
                "request": request,
                "user": user,
                "target_user_id": target_user["id"],
                "username": username,
            },
        )

    @router.get(
        "/~{username}/history",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    async def user_history_page(
        request: Request,
        username: str,
        user: dict = Depends(require_page_permission("can_manage_roles")),
    ):
        target_user = await get_user_by_username(username)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        return templates.TemplateResponse(
            "pages/user-history.html",
            {
                "request": request,
                "user": user,
                "target_user_id": target_user["id"],
                "username": username,
            },
        )

    @router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
    async def settings_page(request: Request, user: dict = Depends(require_page_auth)):
        return templates.TemplateResponse("pages/settings.html", {"request": request, "user": user})

    @router.get("/settings/api-keys", response_class=HTMLResponse, include_in_schema=False)
    async def settings_api_keys_page(request: Request, user: dict = Depends(require_page_auth)):
        return templates.TemplateResponse("pages/settings-api-keys.html", {"request": request, "user": user})

    @router.get("/blog", response_class=HTMLResponse, include_in_schema=False)
    async def blog_list(request: Request, user: dict = Depends(get_page_user)):
        return templates.TemplateResponse(
            "pages/blog-list.html",
            {"request": request, "user": user, "posts": await get_all_posts()},
        )

    @router.get("/blog/{slug}", response_class=HTMLResponse, include_in_schema=False)
    async def blog_post(request: Request, slug: str, user: dict = Depends(get_page_user)):
        post = await get_post(slug)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return templates.TemplateResponse(
            "pages/blog-post.html",
            {"request": request, "user": user, "post": post},
        )

    @router.get("/{state}/municipalities", response_class=HTMLResponse, include_in_schema=False)
    async def municipalities_page(
        request: Request, state: str, user: dict = Depends(get_page_user)
    ):
        return templates.TemplateResponse(
            "pages/municipalities.html",
            {"request": request, "user": user, "state": state, "level": "local"},
        )

    @router.get("/{state}/counties", response_class=HTMLResponse, include_in_schema=False)
    async def counties_page(request: Request, state: str, user: dict = Depends(get_page_user)):
        return templates.TemplateResponse(
            "pages/municipalities.html",
            {"request": request, "user": user, "state": state, "level": "counties"},
        )

    @router.get("/{path:path}/history", response_class=HTMLResponse, include_in_schema=False)
    async def jurisdiction_history_page(
        request: Request,
        path: str,
        identity: Optional[Identity] = Depends(get_optional_user),
    ):
        # Registered ahead of the /{path:path} catch-all, and this one is not optional.
        # `folder_to_jurisdiction_ocdid` only checks `len < 3` — it reads segments 0 and 2 and
        # ignores the rest — so "wa/local/place_seattle/history" parses happily there and would
        # render the jurisdiction page instead of 404ing. Ordering is the only thing between
        # this route and a silently wrong page.
        try:
            jurisdiction_ocdid = _path_to_jurisdiction_ocdid(path)
        except ValueError:
            raise HTTPException(status_code=404, detail="Jurisdiction not found")
        jurisdiction = await get_jurisdiction(jurisdiction_ocdid)
        if not jurisdiction:
            raise HTTPException(status_code=404, detail="Jurisdiction not found")
        user = _build_user_dict(identity)
        if needs_username(user):
            return RedirectResponse("/login/username", status_code=303)
        return templates.TemplateResponse(
            "pages/jurisdiction-history.html",
            {
                "request": request,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                "jurisdiction_name": jurisdiction.get("data", {}).get("name", ""),
                "user": user,
            },
        )

    @router.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def jurisdiction_page(
        request: Request,
        path: str,
        identity: Optional[Identity] = Depends(get_optional_user),
    ):
        try:
            jurisdiction_ocdid = _path_to_jurisdiction_ocdid(path)
        except ValueError:
            raise HTTPException(status_code=404, detail="Jurisdiction not found")
        jurisdiction = await get_jurisdiction(jurisdiction_ocdid)
        if not jurisdiction:
            raise HTTPException(status_code=404, detail="Jurisdiction not found")
        user = _build_user_dict(identity)
        if needs_username(user):
            return RedirectResponse("/login/username", status_code=303)
        return templates.TemplateResponse(
            "pages/jurisdiction.html",
            {
                "request": request,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                "jurisdiction_data": json.dumps(jurisdiction),
                "user": user,
            },
        )

    return router
