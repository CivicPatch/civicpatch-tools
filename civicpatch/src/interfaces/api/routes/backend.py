import asyncio
import json
import traceback
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse

from interfaces.schemas import (
    PeopleCollectorJobRequest,
    validate_people_request
)
from jobs.people_collector.main import start_in_background as start_people_collector_async
from jobs.people_collector.main import stop as stop_people_collector
from jobs.people_collector.schemas import PeopleCollectorContext, WorkflowStatus
from shared.utils import id_utils
from jobs.registry import get_workflow


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/pipelines")
    #@router.post("/jobs/people")
    async def post_pipelines(
        request: PeopleCollectorJobRequest,
        background_tasks: BackgroundTasks,
    ):
        request_id = id_utils.make_request_id()
        warnings, errors = validate_people_request(request)
        background_tasks.add_task(
            start_people_collector_async,
            request_id=request_id,
            jurisdiction_id=request.jurisdiction_id,
            config=request.config,
        )

        return {
            "data": {
                "request_id": request_id,
                "jurisdiction_id": request.jurisdiction_id,
                "message": "Workflow started"
            }
        }

    def generate_status_response(current_state: WorkflowStatus):
        statuses = list(WorkflowStatus)  # Use the enum directly
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
            "data": {
                "status": current_state.value,
                "previous_statuses": previous_statuses,
                "future_statuses": future_statuses,
            }
        }

    @router.get("/pipelines/status")
    async def pipeline_status(
        jurisdiction_id: str,
    ):
        workflow = get_workflow(jurisdiction_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found")

        current_state = (
            workflow.current_state
        )  # This should already be a PipelineStatus instance

        status_response = generate_status_response(current_state)

        return status_response

    @router.get("/sse/pipelines/status")
    async def sse_pipeline_status(
        jurisdiction_ocdid: str,
    ):
        workflow = get_workflow(jurisdiction_ocdid)

        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Initialize the last state tracker
        last_state: Optional[str] = None

        async def sse_generator():
            nonlocal last_state

            while True:
                # 1. Access the current state from the pipeline object
                # Assuming pipeline.context.state is a dictionary or a Pydantic model
                try:
                    # Use .dict() or .model_dump() if it's a Pydantic model
                    # Use getattr() in case the attribute might not exist yet
                    current_response = generate_status_response(workflow.current_state)
                except Exception as e:
                    # Handle cases where context or state might be null/uninitialized
                    print(f"Error accessing workflow state: {e}")
                    current_response = {
                        "data": {"status": "ERROR", "detail": "State access error"}
                    }

                # 2. Check if the state has changed
                # Comparing the Python dictionary objects directly works here.
                if current_response["data"]["status"] != last_state:
                    # 3. A change was detected, format and yield the update
                    # Note: We must encode the message to bytes for the StreamingResponse
                    sse_message = f"data: {json.dumps(current_response)}\n\n"

                    # 4. Update the tracker
                    last_state = current_response["data"]["status"]

                    yield sse_message.encode("utf-8")

                # 5. Pause non-blockingly before checking again
                # Adjust the sleep interval (e.g., 0.5 seconds) based on required responsiveness
                await asyncio.sleep(1)

        # 6. Return the StreamingResponse
        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    @router.post("/pipelines/stop")
    async def stop_pipeline_endpoint(
        jurisdiction_ocdid: str,
    ):
        workflow = get_workflow(jurisdiction_ocdid)
        if workflow is None:
            raise HTTPException(status_code=404, detail="Workflow not found")

        stop_people_collector(jurisdiction_ocdid) 
        return {"status": "stopping", "jurisdiction_id": jurisdiction_id}

    return router
