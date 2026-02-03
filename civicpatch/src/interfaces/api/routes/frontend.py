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

def get_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    REQUIRED_ENV_VARS = [
        #"BRAVE_SEARCH_TOKEN",
        "GOOGLE_SEARCH_TOKEN",
        "GOOGLE_SEARCH_ENGINE_ID",
        #"SERP_API_SEARCH_TOKEN",
        "GOOGLE_GEMINI_TOKEN",
        "OPENAI_TOKEN",
        #"TOGETHER_AI_TOKEN",
        "API_CIVICPATCH_ORG_TOKEN",
        "API_CIVICPATCH_ORG_URL",
    ]

    @router.get("/")
    async def index(request: Request):
        missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
        return templates.TemplateResponse(
            "pages/index.html", {"request": request, "missing_env": missing}
        )

    @router.get("/jurisdictions", include_in_schema=False)
    async def jurisdiction_page(
        request: Request, 
        jurisdiction_ocdid: str
    ):

        print("Rendering jurisdiction page for:", jurisdiction_ocdid)
        history = await civicpatch_api.get_people_job_history(jurisdiction_ocdid)

        return templates.TemplateResponse(
            "pages/jurisdiction.html",
            {
                "request": request,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                "history": json.dumps(history),
            }
        )

    return router