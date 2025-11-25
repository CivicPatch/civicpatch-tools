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
            }
        )

# Don't think this is being called anymore. Delete.
#    @router.post("/pipelines/run", include_in_schema=False)
#    async def pipelines_run(
#        background_tasks: BackgroundTasks,
#        jurisdiction_ocdid: str = Form(...),
#        name: str = Form(...),
#        url: str = Form(...),
#    ):
#        request = PipelineRequest(jurisdiction_id=jurisdiction_ocdid, name=name, url=url)
#        # TODO: expose this to frontend?
#        request_id, _warnings, errors = pipeline_manager.create_pipeline(request)
#
#        try:
#            if len(errors) > 0:
#                # TODO: point to error template
#                raise HTTPException(status_code=400, detail="; ".join(errors))
#
#            await pipeline_manager.start_pipeline(request_id, request, background_tasks)
#
#            return RedirectResponse(
#                url=f"/jurisdictions?jurisdiction_ocdid={jurisdiction_ocdid}", status_code=303
#            )
#
#        except Exception as e:
#            # TODO: point to error template
#            raise HTTPException(status_code=500, detail=str(e))

#    @router.get("/pipelines")
#    async def pipeline_request_page(
#        request: Request, 
#        jurisdiction_ocdid: str
#        ):
#
#        return templates.TemplateResponse(
#            "pages/pipeline_request.html",
#            {
#                "request": request,
#                "jurisdiction_ocdid": jurisdiction_ocdid,
#            },
#        )

#    @router.get("/pipelines/context")
#    async def get_pipeline_context(
#        jurisdiction_ocdid: str
#        ):
#        pipeline_context_file = data_path_utils.get_pipeline_context_file_path(
#            jurisdiction_ocdid
#        )
#        file_like = open(pipeline_context_file, "rb")
#        return StreamingResponse(file_like, media_type="application/json")
#
    return router
#