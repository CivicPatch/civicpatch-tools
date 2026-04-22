import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from database.jurisdictions import get_jurisdiction
from shared.utils.id_utils import folder_to_jurisdiction_ocdid
from schemas.common import Identity, Role
from lib.auth import get_optional_user

_is_production = os.getenv("APP_ENVIRONMENT", "").lower() == "production"


def _build_user_dict(identity: Optional[Identity]) -> dict:
    if not identity:
        return {"authenticated": False, "email": None, "permissions": build_permissions(None)}
    return {
        "authenticated": True,
        "email": identity.email,
        "user_id": identity.user_id,
        "teams": identity.teams or [],
        "permissions": build_permissions(identity),
        "display_name": identity.display_name,
        "avatar_url": (
            f"https://avatars.githubusercontent.com/u/{identity.provider_user_id}"
            if identity.provider == "github" and identity.provider_user_id
            else None
        ),
    }


def build_permissions(identity: Optional[Identity]) -> dict:
    teams = identity.teams or [] if identity else []
    return {
        "can_view_queue_page": Role.MAINTAINERS in teams or Role.CONTRIBUTORS in teams,
        "can_view_queue_page_errors": Role.ADMINS in teams,
        "can_view_jurisdiction_page": Role.DEFAULT in teams,
        "can_scrape_local": not _is_production and Role.MAINTAINERS in teams,
        "can_scrape_remote": Role.MAINTAINERS in teams,
        "can_view_reviews_page": Role.DEFAULT in teams,
        "can_view_issues_page": Role.MAINTAINERS in teams,
        "can_delete_directory_person": Role.CONTRIBUTORS in teams,
        "can_cancel_job": Role.ADMINS in teams,
    }


def get_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    @router.get("/api/permissions", include_in_schema=False)
    async def permissions(identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        return {
            "authenticated": user["authenticated"],
            "permissions": user["permissions"],
            "data": user,
        }

    @router.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        return templates.TemplateResponse("pages/index.html", {"request": request, "user": user})

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

    @router.get("/issues", response_class=HTMLResponse, include_in_schema=False)
    async def issues_page(request: Request, identity: Optional[Identity] = Depends(get_optional_user)):
        user = _build_user_dict(identity)
        if not user["authenticated"] or not user["permissions"]["can_view_issues_page"]:
            return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})
        return templates.TemplateResponse("pages/issues.html", {"request": request, "user": user})

    @router.get("/progress", response_class=HTMLResponse, include_in_schema=False)
    async def progress_page(request: Request):
        return templates.TemplateResponse("pages/progress.html", {"request": request})

    @router.get("/unauthorized", response_class=HTMLResponse, include_in_schema=False)
    async def unauthorized_page(
        request: Request, identity: Optional[Identity] = Depends(get_optional_user)
    ):
        user = _build_user_dict(identity)
        return templates.TemplateResponse("pages/unauthorized.html", {"request": request, "user": user})

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
