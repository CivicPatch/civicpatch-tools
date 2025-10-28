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
from schemas import PipelineRequest
from utils import id_utils, data_path_utils
from pipelines.pipeline_manager import PipelineManager
from pipelines.main import get_pipeline_manager


router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


REQUIRED_ENV_VARS = [
    "BRAVE_SEARCH_TOKEN",
    "GOOGLE_SEARCH_TOKEN",
    "GOOGLE_SEARCH_ENGINE_ID",
    "SERP_API_SEARCH_TOKEN",
    "GOOGLE_GEMINI_TOKEN",
    "OPENAI_TOKEN",
    "TOGETHER_AI_TOKEN",
    "CRUDDER_SHARED_TOKEN",
    "CRUDDER_URL",
]


@router.post("/pipelines/run", include_in_schema=False)
async def pipelines_run(
    background_tasks: BackgroundTasks,
    jurisdiction_id: str = Form(...),
    name: str = Form(...),
    url: str = Form(...),
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
):
    request = PipelineRequest(jurisdiction_id=jurisdiction_id, name=name, url=url)
    # TODO: expose this to frontend?
    _request_id, _warnings, errors = pipeline_manager.create_pipeline(request)

    try:
        if len(errors) > 0:
            # TODO: point to error template
            raise HTTPException(status_code=400, detail="; ".join(errors))

        pipeline_manager.start_pipeline(jurisdiction_id, background_tasks)

        # Redirect to the pipeline request page for this jurisdiction
        jurisdiction_id_url = id_utils.jurisdiction_id_to_slug(jurisdiction_id)

        return RedirectResponse(
            url=f"/pipelines/{jurisdiction_id_url}", status_code=303
        )

    except Exception as e:
        # TODO: point to error template
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipelines/{jurisdiction_id_url}")
async def pipeline_request_page(request: Request, jurisdiction_id_url: str):
    jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_url)

    return templates.TemplateResponse(
        "pipeline_request.html",
        {
            "request": request,
            "jurisdiction_id": jurisdiction_id,
            "jurisdiction_id_url": jurisdiction_id_url,
        },
    )


@router.get("/pipelines/{jurisdiction_id_url}/context")
async def stream_pipeline_context(jurisdiction_id_url: str):
    jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_url)
    pipeline_context_file = data_path_utils.get_pipeline_context_file_path(
        jurisdiction_id
    )
    file_like = open(pipeline_context_file, "rb")
    return StreamingResponse(file_like, media_type="application/json")


@router.get("/")
async def index(request: Request):
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    return templates.TemplateResponse(
        "pages/index.html", {"request": request, "missing_env": missing}
    )
