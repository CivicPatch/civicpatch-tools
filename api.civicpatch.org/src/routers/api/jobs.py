from fastapi import APIRouter
from typing import Optional
from github_service import trigger_github_people_scrape_workflow
import shared.utils.id_utils


def get_router(api_key_header):
    router = APIRouter()

    # Note: lists all jobs started by a specific api key...
#    @router.get(
#        "/",
#        summary="List all jobs",
#        description="Retrieve a list of all jobs with their statuses.",
#    )
#    async def list_jobs(authorization: str = api_key_header):
#        # Implementation to list jobs
#        return {"jobs": []}

    @router.get(
        "/people/{request_id}",
        summary="Get job status",
        description="Retrieve the status of a specific job by its request ID.",
    )
    async def get_job_status(request_id: str):
        # Implementation to get job status
        return {"request_id": request_id, "status": "pending"}

    @router.post(
        "/people",
        summary="Trigger scrape people job",
        description="Trigger a new scrape people job.",
    )
    async def trigger_people_job(
        jurisdiction_ocdid: str, 
        name: Optional[str] = None,
        url: Optional[str] = None
    ):
        # Implementation to trigger a scrape people job
        try:
            request_id = shared.utils.id_utils.make_request_id()
            response = trigger_github_people_scrape_workflow(
                request_id=request_id,
                jurisdiction_ocdid=jurisdiction_ocdid,
                name=name,
                url=url
            )
        except Exception as e:
            print("Error triggering GitHub workflow:", e, response)
            return {"status": "error"}, 500

        return {"request_id": request_id, "status": "started"}

    @router.delete(
        "/people/{request_id}",
        summary="Cancel a job",
        description="Stop a specific job by its request ID.",
    )
    async def stop_job(request_id: str):
        # Implementation to stop a job
        return {"request_id": request_id, "status": "stopped"}

    @router.get(
        "/people/{request_id}/logs",
        summary="Get job logs",
        description="Retrieve logs for a specific job by its request ID.",
    )
    async def get_job_logs(request_id: str):
        # Implementation to get job logs
        return {"request_id": request_id, "logs": []}

    return router