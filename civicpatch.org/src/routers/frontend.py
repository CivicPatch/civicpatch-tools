import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database.jurisdictions import get_jurisdiction
from shared.utils.id_utils import folder_to_jurisdiction_ocdid
from schemas.common import Identity, Role, has_at_least
from lib.auth import get_optional_user
from lib.blog import get_all_posts, get_post

_is_production = os.getenv("APP_ENVIRONMENT", "").lower() == "production"


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
        "can_view_queue_page": has_at_least(role, Role.CONTRIBUTORS),
        "can_view_queue_page_errors": has_at_least(role, Role.ADMINS),
        "can_view_jurisdiction_page": has_at_least(role, Role.DEFAULT),
        "can_scrape_local": not _is_production and has_at_least(role, Role.MAINTAINERS),
        "can_scrape_remote": has_at_least(role, Role.MAINTAINERS),
        "can_view_reviews_page": has_at_least(role, Role.DEFAULT),
        "can_view_issues_page": has_at_least(role, Role.ADMINS),
        "can_view_activity_page": has_at_least(role, Role.DEFAULT),
        "can_view_quarantine": has_at_least(role, Role.MAINTAINERS),
        "can_delete_directory_person": has_at_least(role, Role.CONTRIBUTORS),
        "can_close_pull_request": has_at_least(role, Role.CONTRIBUTORS),
        "can_cancel_job": has_at_least(role, Role.ADMINS),
        "can_write_config": has_at_least(role, Role.MAINTAINERS),
        "can_write_global_config": has_at_least(role, Role.ADMINS),
        "can_manage_roles": has_at_least(role, Role.ADMINS),
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
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/queue.html", {"request": request, "user": user})

    @router.get("/review", response_class=HTMLResponse, include_in_schema=False)
    async def review_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_reviews_page"]:
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/review.html", {"request": request, "user": user})

    @router.get("/review/session", response_class=HTMLResponse, include_in_schema=False)
    async def review_session_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_reviews_page"]:
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/review-session.html", {"request": request, "user": user})

    @router.get("/issues", response_class=HTMLResponse, include_in_schema=False)
    async def issues_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_issues_page"]:
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/issues.html", {"request": request, "user": user})

    @router.get("/activity", response_class=HTMLResponse, include_in_schema=False)
    async def activity_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_activity_page"]:
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/activity.html", {"request": request, "user": user})

    @router.get("/config-editor-demo", response_class=HTMLResponse, include_in_schema=False)
    async def config_editor_demo(request: Request):
        return templates.TemplateResponse("pages/config-editor-demo.html", {"request": request})

    @router.get("/roles", response_class=HTMLResponse, include_in_schema=False)
    async def roles_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_write_config"]:
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/roles.html", {"request": request, "user": user})

    @router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
    async def admin_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_manage_roles"]:
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/admin.html", {"request": request, "user": user})

    @router.get("/settings", response_class=HTMLResponse, include_in_schema=False)
    async def settings_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"]:
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/settings.html", {"request": request, "user": user})

    @router.get("/progress", response_class=HTMLResponse, include_in_schema=False)
    async def progress_page(request: Request):
        return templates.TemplateResponse("pages/progress.html", {"request": request})

    @router.get("/unauthorized", response_class=HTMLResponse, include_in_schema=False)
    async def unauthorized_page(
        request: Request, identity: Optional[Identity] = Depends(get_optional_user)
    ):
        user = _build_user_dict(identity)
        return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})

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

    @router.get("/{path:path}", response_class=HTMLResponse, include_in_schema=False)
    async def jurisdiction_page(
        request: Request,
        path: str,
        identity: Optional[Identity] = Depends(get_optional_user),
    ):
        try:
            jurisdiction_ocdid = folder_to_jurisdiction_ocdid(path)
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
