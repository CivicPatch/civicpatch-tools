from fastapi import (
    APIRouter,
    Form,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
)
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from shared.utils import data_path_utils
from shared.utils import id_utils
import services.civicpatch_api as civicpatch_api
import json
import httpx
from civicpatch_environment import get_env_vars

async def get_current_user(request: Request):
    try:
        user = await civicpatch_api.get_me(request)
        permissions = build_permissions(user)
        return {
            "authenticated": user.get("authenticated", False),
            "email": user.get("email"),
            "teams": user.get("teams", []),
            "permissions": permissions,
            "display_name": user.get("display_name"),
            "avatar_url": user.get("avatar_url"),
        }
    except (httpx.ConnectError, httpx.TimeoutException):
        return {"authenticated": False, "email": None, "permissions": {}}


def build_permissions(user_data: dict) -> dict:
    teams = user_data.get("teams", [])
    return {
        "can_view_jobs_page_errors": "admins" in teams,

        "can_view_jobs_page": any(t in teams for t in ("maintainers", "contributors")),

        "can_view_jurisdiction_page": "default" in teams,
        "can_scrape_local": civicpatch_api.can_scrape_locally(),
        "can_scrape_remote": "maintainers" in teams,

        "can_view_reviews_page": "default" in teams,

        "can_delete_directory_person": any(t in teams for t in ("contributors", "maintainers", "admins")),
    }


def get_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    REQUIRED_ENV_VARS = [
        # For local scrapes only
        #"GOOGLE_SEARCH_TOKEN",
        #"GOOGLE_SEARCH_ENGINE_ID",
        #"GOOGLE_GEMINI_TOKEN",
        #"OPENAI_TOKEN",

        "SERVICE_API_KEY",
        "API_CIVICPATCH_ORG_URL",
    ]

    @router.get("/")
    async def index(
        request: Request,
        user: dict = Depends(get_current_user)
    ):
        env = get_env_vars()
        missing = [var for var in REQUIRED_ENV_VARS if not env.get(var)]
        return templates.TemplateResponse(
            "pages/index.html", {"request": request, "missing_env": missing, "user": user}
        )

    @router.get("/jurisdictions", include_in_schema=False)
    async def jurisdiction_page(
        request: Request,
        jurisdiction_ocdid: str,
        user: dict = Depends(get_current_user)
    ):
        try:
            jurisdiction = await civicpatch_api.get_jurisdiction(jurisdiction_ocdid, request)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="Jurisdiction not found")
            raise

        return templates.TemplateResponse(
            "pages/jurisdiction.html",
            {
                "request": request,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                "jurisdiction_data": json.dumps(jurisdiction),
                "user": user,
            }
        )

    @router.get("/progress", include_in_schema=False)
    async def progress_page(
        request: Request,
    ):
        return templates.TemplateResponse(
            "pages/progress.html",
            {
                "request": request,
            }
        )

    @router.get("/jobs", include_in_schema=False)
    async def jobs_page(
        request: Request,
        user: dict = Depends(get_current_user)
    ):
        if not user.get("authenticated") or not user.get("permissions", {}).get("can_view_jobs_page"):
            return templates.TemplateResponse(
                "pages/unauthorized.html",
                {"request": request, "user": user}
            )
        return templates.TemplateResponse(
            "pages/jobs.html",
            {"request": request, "user": user}
        )

    @router.get("/review", include_in_schema=False)
    async def review_page(
        request: Request,
        user: dict = Depends(get_current_user)
    ):
        if not user.get("authenticated") or not user.get("permissions", {}).get("can_view_reviews_page"):
            return templates.TemplateResponse(
                "pages/unauthorized.html",
                {"request": request, "user": user}
            )
        return templates.TemplateResponse(
            "pages/review.html",
            {"request": request, "user": user}
        )

    return router
