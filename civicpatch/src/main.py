from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
from utils.pipeline_utils import get_municipalities_to_scrape
from pipeline import Pipeline, PipelineStatus, get_pipeline_status_by_jurisdiction_id
from auth.token_handler import verify_github_action_data_query
from utils import id_utils, log_utils
from schemas import PipelineRequest
import os
from utils import data_path_utils
import json
from fastapi.responses import RedirectResponse, StreamingResponse
import time

app = FastAPI()
app.mount("/static", StaticFiles(directory="src/static"), name="static")
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

class SearchRequest(BaseModel):
    state: str
    num: int = 0

# Internal usage only
@app.get("/api/search")
async def search_endpoint(
    state: str,
    num: int = 0,
    jurisdiction_ids_to_ignore: Optional[List[str]] = None
):
    """TODO: Make call to crudder"""
    pass
    # jurisdiction_ids = get_municipalities_to_scrape(
    #     state.lower(), 
    #     num, 
    #     jurisdiction_ids_to_ignore
    # )
    # if len(jurisdiction_ids) == 0:
    #     raise HTTPException(
    #         status_code=404,
    #         detail=f"No municipalities found for state {state}"
    #     )
    # return {"jurisdiction_ids": jurisdiction_ids}

def run_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks, with_debug = False):    
    request_id = id_utils.make_request_id()
    jurisdiction_id = request.jurisdiction_id
    jurisdiction_id_obj= id_utils.parse_jurisdiction_id(jurisdiction_id)
    warnings: List[str] = []
    errors: List[str] = []

    if not jurisdiction_id_obj:
        errors.append(f"Invalid jurisdiction_id format: {jurisdiction_id}")
    if not request.name:
        warnings.append("Missing 'name' field: A name and legal status (e.g., 'Seattle city') is preferred for search purposess. Substituting with place name jurisdiction_id.")
    if not request.url:
        errors.append("Missing 'url' field")

    pipeline_state = get_pipeline_status_by_jurisdiction_id(jurisdiction_id)
    if not with_debug and pipeline_state is not None:
        print(f"{jurisdiction_id}/{request_id}: Found existing pipeline with state: {pipeline_state}, cancelling job...")
        raise Exception("Pipeline already running for this jurisdiction")

    if len(errors) == 0:
        pipeline = Pipeline(pipeline_state=PipelineStatus.INIT)
        background_tasks.add_task(pipeline.run, request_id, request)

    return request_id, warnings, errors

# Internal usage only
@app.post("/api/pipeline")
async def pipeline_endpoint(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run pipeline for a specific municipality"""
    try:
        request_id, warnings, errors = run_pipeline(request, background_tasks)

        if len(errors) > 0:
            raise HTTPException(
                status_code = 400,
                detail="; ".join(errors)
            )

        response = {
            "status": "started",
            "request_id": request_id,
        }

        if len(warnings) > 0:
            response["warnings"] = warnings
        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
@app.get("/api/pipeline/{jurisdiction_id}/status")
async def pipeline_status(jurisdiction_id: str):
    pipeline_state = get_pipeline_status_by_jurisdiction_id(jurisdiction_id)
    if pipeline_state is None:
        raise HTTPException(
            status_code=404,
            detail="Pipeline not found"
        )
    
    statuses = [PipelineStatus.INIT.value, 
                PipelineStatus.RESEARCH_MUNICIPALITY.value, 
                PipelineStatus.SEARCH_LINKS.value, 
                PipelineStatus.SCRAPE_PAGE.value,
                PipelineStatus.PREPROCESS_PAGE_CONTENT.value,
                PipelineStatus.PROCESS_PAGE_CONTENT.value,
                PipelineStatus.MERGE_RECORDS_WITHIN_LLM.value,
                PipelineStatus.MERGE_RECORDS_ACROSS_LLMS.value,
                PipelineStatus.MAYBE_SEND_TO_GITHUB.value,
                PipelineStatus.CLEANUP.value,
                PipelineStatus.DONE.value]
    previous_statuses = [status for status in statuses if statuses.index(status) < statuses.index(pipeline_state.value)]
    future_statuses = [status for status in statuses if statuses.index(status) > statuses.index(pipeline_state.value)]

    return {"status": pipeline_state, 
            "previous_statuses": previous_statuses, 
            "future_statuses": future_statuses}

@app.post("/pipelines/run", include_in_schema=False)
async def pipelines_run(
    background_tasks: BackgroundTasks,
    jurisdiction_id: str = Form(...),
    name: str = Form(...),
    url: str = Form(...),
):
    request = PipelineRequest(jurisdiction_id=jurisdiction_id, name=name, url=url)
    request_id, _warnings, errors = run_pipeline(request, background_tasks)
    errors = []

    try:
        if len(errors) > 0:
            # TODO: point to error template
            raise HTTPException(
                status_code = 400,
                detail="; ".join(errors)
            )

        # Redirect to the pipeline request page for this jurisdiction
        jurisdiction_id_url = id_utils.jurisdiction_id_to_slug(jurisdiction_id)

        return RedirectResponse(
            url=f"/pipelines/{jurisdiction_id_url}",
            status_code=303
        )

    except Exception as e:
        # TODO: point to error template
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/pipelines/{jurisdiction_id_url}")
async def pipeline_request_page(request: Request, jurisdiction_id_url: str):
    jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_url)

    return templates.TemplateResponse("pipeline_request.html", {
        "request": request, 
        "jurisdiction_id": jurisdiction_id,
        "jurisdiction_id_url": jurisdiction_id_url
    })

@app.get("/pipelines/{jurisdiction_id_url}/context")
async def stream_pipeline_context(jurisdiction_id_url: str):
    jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_url)
    pipeline_context_file = data_path_utils.get_pipeline_context_file_path(jurisdiction_id)
    file_like = open(pipeline_context_file, "rb")
    return StreamingResponse(file_like, media_type="application/json")

@app.get("/")
async def index(request: Request):
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    return templates.TemplateResponse("index.html", {"request": request, "missing_env": missing})