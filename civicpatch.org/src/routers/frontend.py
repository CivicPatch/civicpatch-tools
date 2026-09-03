import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database.jurisdictions import get_jurisdiction
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
        "display_name": identity.display_name,
        "avatar_url": None,
    }


def build_permissions(identity: Optional[Identity]) -> dict:
    role = identity.role if identity else None
    return {
        "can_view_queue_page": has_at_least(role, UserRole.CONTRIBUTORS),
        "can_view_queue_page_errors": has_at_least(role, UserRole.ADMINS),
        # One key, because the caller no longer picks a mode: the environment does, server
        # side. Whether you may scrape is a role question; how it dispatches is not.
        "can_scrape": has_at_least(role, UserRole.MAINTAINERS),
        "can_view_reviews_page": has_at_least(role, UserRole.DEFAULT),
        "can_view_issues_page": has_at_least(role, UserRole.ADMINS),
        "can_view_activity_page": has_at_least(role, UserRole.DEFAULT),
        "can_view_quarantine": has_at_least(role, UserRole.MAINTAINERS),
        "can_edit_jurisdiction_data": has_at_least(role, UserRole.MAINTAINERS),
        "can_delete_directory_person": has_at_least(role, UserRole.CONTRIBUTORS),
        "can_reject_scrape": has_at_least(role, UserRole.CONTRIBUTORS),
        "can_cancel_pipeline_run": has_at_least(role, UserRole.ADMINS),
        # Same boundary as cancelling, but a separate key: reading why a run is stuck and
        # stopping it are different acts, and the frontend uses this one to decide whether to
        # poll at all rather than fire a rejected request every few seconds.
        "can_view_temporal_workflow_state": has_at_least(role, UserRole.ADMINS),
        "can_write_config": has_at_least(role, UserRole.MAINTAINERS),
        "can_write_global_config": has_at_least(role, UserRole.ADMINS),
        "can_manage_roles": has_at_least(role, UserRole.ADMINS),
    }


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
    async def index(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        return templates.TemplateResponse(
            "pages/index.html", {"request": request, "user": user, "posts": (await get_all_posts())[:3]}
        )

    @router.get("/login", response_class=HTMLResponse, include_in_schema=False)
    async def login_page(
        request: Request, identity: Optional[Identity] = Depends(get_optional_user)
    ):
        user = _build_user_dict(identity)
        return templates.TemplateResponse(
            "pages/login.html",
            {
                "request": request,
                "user": user,
            },
        )

    @router.get("/queue", response_class=HTMLResponse, include_in_schema=False)
    async def queue_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_queue_page"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/queue.html", {"request": request, "user": user})

    @router.get("/review", response_class=HTMLResponse, include_in_schema=False)
    async def review_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_reviews_page"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/review.html", {"request": request, "user": user})

    @router.get("/review/session", response_class=HTMLResponse, include_in_schema=False)
    async def review_session_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_reviews_page"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/review-session.html", {"request": request, "user": user})

    @router.get("/issues", response_class=HTMLResponse, include_in_schema=False)
    async def issues_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_issues_page"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/issues.html", {"request": request, "user": user})

    # `/activity` is a section, not a page: the change log and the cross-state changeset
    # summary are two views of "what has been happening". The bare path redirects rather than
    # 404ing, because it was the change log's own URL until this split.
    @router.get("/activity", response_class=HTMLResponse, include_in_schema=False)
    async def activity_index(request: Request):
        return RedirectResponse("/activity/changelogs", status_code=303)

    @router.get("/activity/changelogs", response_class=HTMLResponse, include_in_schema=False)
    async def activity_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_activity_page"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/activity.html", {"request": request, "user": user})

    @router.get("/roles", response_class=HTMLResponse, include_in_schema=False)
    async def roles_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_write_config"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/roles.html", {"request": request, "user": user})

    @router.get("/imports", response_class=HTMLResponse, include_in_schema=False)
    async def imports_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_write_config"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/imports.html", {"request": request, "user": user})

    @router.get("/activity/changesets", response_class=HTMLResponse, include_in_schema=False)
    async def changesets_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        # Same gate as the change log beside it — the section is one thing. The scrape control
        # this page carries is gated separately, on `can_scrape`.
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_activity_page"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/changesets.html", {"request": request, "user": user})

    @router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
    async def admin_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_manage_roles"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/admin.html", {"request": request, "user": user})

    @router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
    async def settings_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"]:
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("pages/settings.html", {"request": request, "user": user})

    @router.get("/blog", response_class=HTMLResponse, include_in_schema=False)
    async def blog_list(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        return templates.TemplateResponse(
            "pages/blog-list.html",
            {"request": request, "user": user, "posts": await get_all_posts()},
        )

    @router.get("/blog/{slug}", response_class=HTMLResponse, include_in_schema=False)
    async def blog_post(request: Request, slug: str, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        post = await get_post(slug)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        return templates.TemplateResponse(
            "pages/blog-post.html",
            {"request": request, "user": user, "post": post},
        )

    @router.get("/{state}/local", response_class=HTMLResponse, include_in_schema=False)
    async def municipalities_page(
        request: Request, state: str, identity: Optional[Identity] = Depends(get_optional_user)
    ):
        # Registered ahead of the /{path:path} catch-all below — that route requires
        # >=3 path segments (folder_to_jurisdiction_ocdid), so a bare "{state}/local"
        # would otherwise 404 there instead of reaching this page. Page content lands
        # in a later commit; this just claims the route.
        user = _build_user_dict(identity)
        return templates.TemplateResponse(
            "pages/municipalities.html", {"request": request, "user": user, "state": state}
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
