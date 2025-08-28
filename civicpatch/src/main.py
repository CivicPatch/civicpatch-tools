import asyncio
from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from utils.pipeline_utils import get_municipalities_to_scrape
from pipeline import Pipeline, PipelineStatus
from auth.token_handler import verify_github_action_data_query
import uuid

app = FastAPI()

class SearchRequest(BaseModel):
    state: str
    num: int = 0
    geoids_to_ignore: Optional[List[str]] = None

class PipelineRequest(BaseModel):
    state: str
    geoid: str

# Internal usage only
@app.post("/api/search")
async def search_endpoint(request: SearchRequest):
    """Search for municipalities to scrape"""
    geoids = get_municipalities_to_scrape(
        request.state.lower(), 
        request.num, 
        request.geoids_to_ignore
    )
    if len(geoids) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No municipalities found for state {request.state}"
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
        return {"status": "started"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

# GitHub Actions endpoint - requires authentication
@app.post("/api/github-actions")
async def github_actions_endpoint(
    request: Request,
):
    """
    GitHub Actions endpoint - requires authentication
    See: https://docs.github.com/en/rest/actions/workflows
    """
    timestamp = request.headers.get("X-Timestamp")
    signature = request.headers.get("X-Signature")

    if not timestamp or not signature:
        raise HTTPException(
            status_code=401,
            detail="Missing required headers: X-Timestamp and X-Signature"
        )

    body = (await request.body()).decode() or ""
    authorized = verify_github_action_data_query(timestamp=timestamp, signature=signature, body=body)

    if authorized is False:
        raise HTTPException(
            status_code=401,
            detail="Invalid signature"
        )

    try:
        # TODO: package everything up into zip file under .github_actions_data folder
        return {
            "request_id": str(uuid.uuid4()),
            "status": "success",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

