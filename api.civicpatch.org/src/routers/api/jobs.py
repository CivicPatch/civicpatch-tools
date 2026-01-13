from fastapi import APIRouter
from typing import Optional
from pydantic import BaseModel
from github_service import trigger_people_job_workflow 
from database import (
    get_job,
    get_job_status,
    update_job_status,
    create_job
)
import shared.utils.id_utils


def get_router(api_key_header):
    router = APIRouter()

    @router.get(
        "/people/{request_id}",
        summary="Get job results, if available",
        description="Retrieve the status of a specific job by its request ID.",
    )
    async def get_job_endpoint(request_id: str):
        job = await get_job(request_id)
        if job:
            return {
                "request_id": request_id,
                "status": job['status'],
                "progress": job['progress'],
                "arguments": job['arguments_json'],
                "result": job['result_json'],
                "created_at": job['created_at'],
                "updated_at": job['updated_at']
            }
        else:
            return {"error": "Job not found"}, 404
    @router.get(
        "/people/{request_id}/status",
        summary="Get job status and progress",
        description="Retrieve the progress of a specific job by its request ID.",
    )
    async def get_job_status_endpoint(request_id: str):
        response = await get_job_status(request_id)
        return {
            "request_id": request_id,
            "status": response['status'],
            "progress": response['progress']
        }

    class UpdateJobStatusRequest(BaseModel):
        status: str
        progress: str

    @router.patch(
        "/people/{request_id}",
        summary="Update job status and progress",
        description="Update status and/or progress of a specific job by its request ID.",
    )
    async def patch_job_status_endpoint(
        request_id: str,
        request: UpdateJobStatusRequest
    ):
        await update_job_status(request_id, status=request.status, progress=request.progress)
        return {"request_id": request_id, "status": request.status, "progress": request.progress}


    class CreatePeopleJobRequest(BaseModel):
        jurisdiction_ocdid: str
        name: Optional[str] = None
        url: str
    @router.post(
        "/people",
        summary="Trigger scrape people job",
        description="Trigger a new scrape people job.",
    )
    async def create_people_job_endpoint(
        request: CreatePeopleJobRequest
    ):
        try:
            request_id = shared.utils.id_utils.make_request_id()
            await create_job(
                request_id,
                job_type="people",
                arguments_json={
                    "jurisdiction_ocdid": request.jurisdiction_ocdid,
                    "name": request.name,
                    "url": request.url
                }
            )
            response = trigger_people_job_workflow(
                request_id=request_id,
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                name=request.name,
                url=request.url
            )
        except Exception as e:
            print(f"Error triggering people job: {e}")
            return {"status": "error"}, 500

        return {"request_id": request_id, "status": "started"}

    @router.delete(
        "/people/{request_id}",
        summary="Cancel a job",
        description="Stop a specific job by its request ID.",
    )
    async def stop_job_endpoint(request_id: str):
        # Implementation to stop a job
        # TBD
        return {"request_id": request_id, "status": "stopped"}

    return router