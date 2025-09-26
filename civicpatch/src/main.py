import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
from utils.pipeline_utils import get_municipalities_to_scrape
from pipeline import Pipeline, PipelineStatus
from auth.token_handler import verify_github_action_data_query
from utils import id_utils
from schemas import PipelineRequest
import os

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

# Internal usage only
@app.post("/api/pipeline")
async def pipeline_endpoint(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run pipeline for a specific municipality"""
    try:
        pipeline = Pipeline(pipeline_state=PipelineStatus.INIT)
        request_id = id_utils.make_request_id()
        jurisdiction_id = id_utils.parse_jurisdiction_id(request.jurisdiction_id)
        warnings: List[str] = []

        if not jurisdiction_id:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid jurisdiction_id format: {request.jurisdiction_id}"
            )
        
        if not request.url:
            raise HTTPException(
                status_code=400,
                detail="Missing 'url' field."
            )
        
        if not request.name:
            warnings.append("Missing 'name' field: A name and legal status (e.g., 'Seattle city') is preferred for search purposess. Substituting with place name jurisdiction_id.")

        background_tasks.add_task(pipeline.run_async, request_id, request)
        response = {"status": "started",
                    "request_id": request_id}
        if len(warnings) > 0:
            response["warnings"] = warnings
        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.get("/")
async def index(request: Request):
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    return templates.TemplateResponse("index.html", {"request": request, "missing_env": missing})

# TODO
# @app.get("/api/pipeline/{request_id}")