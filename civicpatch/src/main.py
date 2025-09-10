import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Optional
from utils.pipeline_utils import get_municipalities_to_scrape
from pipeline import Pipeline, PipelineStatus
from auth.token_handler import verify_github_action_data_query
import uuid
import os

app = FastAPI()
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
    geoids_to_ignore: Optional[List[str]] = None

class PipelineRequest(BaseModel):
    state: str
    geoid: str

# Internal usage only
@app.get("/api/search")
async def search_endpoint(
    state: str,
    num: int = 0,
    geoids_to_ignore: Optional[List[str]] = None
):
    geoids = get_municipalities_to_scrape(
        state.lower(), 
        num, 
        geoids_to_ignore
    )
    if len(geoids) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No municipalities found for state {state}"
        )
    return {"geoids": geoids}

# Internal usage only
@app.post("/api/pipeline")
async def pipeline_endpoint(request: PipelineRequest, background_tasks: BackgroundTasks):
    """Run pipeline for a specific municipality"""
    try:
        pipeline = Pipeline(pipeline_state=PipelineStatus.INIT)
        request_id = str(uuid.uuid4())
        background_tasks.add_task(pipeline.run, request_id, request.state.lower(), request.geoid)
        return {"status": "started",
                "request_id": request_id}
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