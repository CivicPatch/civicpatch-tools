from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from typing import List, Optional
from pipelines.pipeline import (
    PipelineStatus,
)
from pipelines.pipeline_manager import PipelineManager
from pipelines.main import get_pipeline_manager
from schemas import PipelineRequest
import traceback
from utils import id_utils

router = APIRouter()


# Internal usage only
@router.get("/jurisdictions")
async def get_jurisdictions(
    state: str, num: int = 0, jurisdiction_ids_to_ignore: Optional[List[str]] = None
):
    """TODO: Make call to crudder"""
    pass


# This will ALWAYS start a new pipeline
@router.post("/pipelines")
async def post_pipelines(
    request: PipelineRequest,
    background_tasks: BackgroundTasks,
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
):
    """Always create and start a new pipeline for a specific municipality."""
    try:
        # Create a new pipeline
        request_id, warnings, errors = pipeline_manager.create_pipeline(request)

        if len(errors) > 0:
            raise HTTPException(status_code=400, detail="; ".join(errors))

        # Start the pipeline
        pipeline_manager.start_pipeline(request.jurisdiction_id, background_tasks)

        return {
            "status": "started",
            "request_id": request_id,
            "warnings": warnings,
        }

    except Exception as e:
        # Log the stack trace for debugging
        stack_trace = traceback.format_exc()
        print(f"Error: {e}")
        print(f"Stack Trace: {stack_trace}")

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline/{jurisdiction_id_url}/status")
async def pipeline_status(
    jurisdiction_id_url: str,
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
):
    jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_url)
    pipeline = pipeline_manager.get_pipeline(jurisdiction_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    statuses = list(PipelineStatus)  # Use the enum directly
    current_state = (
        pipeline.context.state
    )  # This should already be a PipelineStatus instance

    previous_statuses = [
        status.value
        for status in statuses
        if statuses.index(status) < statuses.index(current_state)
    ]
    future_statuses = [
        status.value
        for status in statuses
        if statuses.index(status) > statuses.index(current_state)
    ]

    return {
        "status": current_state.value,  # Return the string value of the current state
        "previous_statuses": previous_statuses,
        "future_statuses": future_statuses,
    }


@router.post("/pipelines/{jurisdiction_id_url}/stop")
async def stop_pipeline_endpoint(
    jurisdiction_id_url: str,
    pipeline_manager: PipelineManager = Depends(get_pipeline_manager),
):
    jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_url)
    pipeline_manager.stop_pipeline(jurisdiction_id)
    return {"status": "stopping", "jurisdiction_id": jurisdiction_id}
