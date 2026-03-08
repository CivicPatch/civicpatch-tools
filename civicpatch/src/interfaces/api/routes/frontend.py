import os
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

API_URL = os.getenv("API_CIVICPATCH_ORG_URL", "http://localhost:8001")

async def get_current_user(request: Request):
    data = await civicpatch_api.get_me(request)
    return data

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
        missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
        return templates.TemplateResponse(
            "pages/index.html", {"request": request, "missing_env": missing, "user": user}
        )

    @router.get("/jurisdictions", include_in_schema=False)
    async def jurisdiction_page(
        request: Request, 
        jurisdiction_ocdid: str,
        user: dict = Depends(get_current_user)
    ):
        history = await civicpatch_api.get_people_job_history(jurisdiction_ocdid, request)

        return templates.TemplateResponse(
            "pages/jurisdiction.html",
            {
                "request": request,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                "history": json.dumps(history),
                "user": user
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
        return templates.TemplateResponse(
            "pages/jobs.html",
            {
                "request": request,
                "user": user,
            }
        )

    return router