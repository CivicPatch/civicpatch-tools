import json

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pipelines.pipeline import (
    PipelineStatus,
)
from pipelines.pipeline_manager import PipelineManager
from schemas import PipelineRequest
import traceback
import asyncio
from utils import id_utils


def get_router(pipeline_manager: PipelineManager) -> APIRouter:
    router = APIRouter()

    @router.post("/pipelines/{jurisdiction_ocdid_slug}")
    async def post_pipelines(
        jurisdiction_ocdid_slug: str,
        request: PipelineRequest,
        background_tasks: BackgroundTasks,
    ):
        try:
            existing_pipeline = pipeline_manager.get_pipeline(
                request.jurisdiction_id
            )
            if existing_pipeline:
                raise HTTPException(
                    status_code=400,
                    detail=f"Pipeline for jurisdiction {request.jurisdiction_id} already exists. Status: {existing_pipeline.context.state.value}",
                )

            # Create a new pipeline
            request_id, warnings, errors = await pipeline_manager.create_start_pipeline(request, background_tasks)

            if len(errors) > 0:
                raise HTTPException(status_code=400, detail="; ".join(errors))

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

    def generate_status_response(current_state: PipelineStatus):
        statuses = list(PipelineStatus)  # Use the enum directly
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

    @router.get("/pipelines/{jurisdiction_id_slug}/status")
    async def pipeline_status(
        jurisdiction_id_slug: str,
    ):
        jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_slug)
        pipeline = pipeline_manager.get_pipeline(jurisdiction_id)
        if pipeline is None:
            raise HTTPException(status_code=404, detail="Pipeline not found")

        current_state = (
            pipeline.context.state
        )  # This should already be a PipelineStatus instance


        status_response = generate_status_response(current_state) 

        return status_response 

    @router.get("/sse/pipelines/{jurisdiction_id_slug}/status")
    async def sse_pipeline_status(
        jurisdiction_id_slug: str,
    ):
        jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_slug)
        pipeline = pipeline_manager.get_pipeline(jurisdiction_id)

        if pipeline is None:
            raise HTTPException(status_code=404, detail="Pipeline not found")

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
                    current_response = generate_status_response(pipeline.context.state)
                except Exception as e:
                    # Handle cases where context or state might be null/uninitialized
                    print(f"Error accessing pipeline state: {e}")
                    current_response = {"data": {"status": "ERROR", "detail": "State access error"}}


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
        return StreamingResponse(
            sse_generator(),
            media_type="text/event-stream"
        )

    @router.post("/pipelines/{jurisdiction_id_url}/stop")
    async def stop_pipeline_endpoint(
        jurisdiction_id_url: str,
    ):
        jurisdiction_id = id_utils.slug_to_jurisdiction_id(jurisdiction_id_url)
        pipeline_manager.stop_pipeline(jurisdiction_id)
        return {"status": "stopping", "jurisdiction_id": jurisdiction_id}

    return router
