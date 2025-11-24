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
from shared.utils import data_path_utils
from shared.utils import id_utils
from pipelines.pipeline_manager import PipelineManager

def get_router(templates: Jinja2Templates, pipeline_manager: PipelineManager) -> APIRouter:
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

        return templates.TemplateResponse(
            "pages/jurisdiction.html",
            {
                "request": request,
                "jurisdiction_ocdid": jurisdiction_ocdid,
                "jurisdiction_ocdid_slug": id_utils.jurisdiction_id_to_slug(jurisdiction_ocdid),
            }
        )

    @router.post("/pipelines/run", include_in_schema=False)
    async def pipelines_run(
        background_tasks: BackgroundTasks,
        jurisdiction_id: str = Form(...),
        name: str = Form(...),
        url: str = Form(...),
    ):
        request = PipelineRequest(jurisdiction_id=jurisdiction_id, name=name, url=url)
        # TODO: expose this to frontend?
        request_id, _warnings, errors = pipeline_manager.create_pipeline(request)

        try:
            if len(errors) > 0:
                # TODO: point to error template
                raise HTTPException(status_code=400, detail="; ".join(errors))

            await pipeline_manager.start_pipeline(request_id, request, background_tasks)

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
            "pages/pipeline_request.html",
            {
                "request": request,
                "jurisdiction_id": jurisdiction_id,
                "jurisdiction_id_url": jurisdiction_id_url,
            },
        )

    @router.get("/pipelines/{jurisdiction_id_url}/context")
    async def get_pipeline_context(jurisdiction_id_url: str):
        jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_url)
        pipeline_context_file = data_path_utils.get_pipeline_context_file_path(
            jurisdiction_id
        )
        file_like = open(pipeline_context_file, "rb")
        return StreamingResponse(file_like, media_type="application/json")

    return router
