from fastapi import APIRouter, Depends 
from fastapi.responses import JSONResponse
from typing import Optional, Any
from pydantic import BaseModel
from schemas import Identity
from github_service import trigger_people_job_workflow 
from services.api_service import can_make_api_request
from database import (
    get_job,
    get_job_status,
    update_job_status,
    register_job,
    update_job_result,
)
from utils.auth import get_user
import shared.utils.id_utils

class GetJobResponse(BaseModel):
    request_id: str
    status: str
    progress: int
    arguments: dict
    result: Optional[Any] = None
    pull_request_url: Optional[str] = None # TODO: implement
    created_at: str
    updated_at: str

class GetJobStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: int

class UpdateJobStatusRequest(BaseModel):
    status: str
    progress: Optional[int]

class UpdateJobStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: Optional[int] = None

class CreateJobResponse(BaseModel):
    request_id: str
    status: str

class CreatePeopleRegisterJobRequest(BaseModel):
    request_id: str
    arguments: dict
    server_source: Optional[str] = None

class DeleteJobResponse(BaseModel):
    request_id: str
    status: str

class PostJobResultRequest(BaseModel):
    data: Any

class ErrorResponse(BaseModel):
    error: str

def get_router(api_key_header):
    router = APIRouter()

    @router.get(
        "/people/{request_id}",
        summary="Get job and job results, if available",
        description="Retrieve the status of a specific job by its request ID.",
        response_model=GetJobResponse | ErrorResponse
    )
    async def get_job_endpoint(request_id: str):
        job = await get_job(request_id)
        print("job fetched:", job)
        if job:
            return GetJobResponse(
                request_id=request_id,
                status=job['status'],
                progress=job['progress'],
                arguments=job['arguments_json'],
                result=job['result_json'],
                pull_request_url=job['pull_request_url'],
                created_at=job['created_at'],
                updated_at=job['updated_at']
            )
        else:
            return JSONResponse(
                content=ErrorResponse(error="Job not found").model_dump(),
                status_code=404
            )

    @router.get(
        "/people/{request_id}/status",
        summary="Get job status and progress",
        description="Retrieve the progress of a specific job by its request ID.",
        response_model=GetJobStatusResponse
    )
    async def get_job_status_endpoint(request_id: str):
        response = await get_job_status(request_id)
        return GetJobStatusResponse(
            request_id=request_id,
            status=response['status'],
            progress=response['progress']
        )

    @router.patch(
        "/people/{request_id}/status",
        summary="Update job status and progress",
        description="Update status and/or progress of a specific job by its request ID.",
        include_in_schema=False
    )
    async def patch_job_status_endpoint(
        request_id: str,
        request: UpdateJobStatusRequest
    ):
        await update_job_status(request_id, status=request.status, progress=request.progress)
        return UpdateJobStatusResponse(
            request_id=request_id,
            status=request.status,
            progress=request.progress
        )

    class CreatePeopleJobRequest(BaseModel):
        jurisdiction_ocdid: str
        name: Optional[str] = None
        url: str
    @router.post(
        "/people",
        summary="Trigger scrape people job",
        description="Trigger a new scrape people job.",
        response_model=CreateJobResponse,
    )
    async def create_people_job_endpoint(
        request: CreatePeopleJobRequest,
        user: Identity = Depends(get_user)
    ):
        api_request_allowed, reason = await can_make_api_request(user.provider, user.provider_user_id)
        if not api_request_allowed:
            return JSONResponse(
                content=ErrorResponse(error=reason).model_dump(),
                status_code=429
            )

        try:
            request_id = shared.utils.id_utils.make_request_id() 
            response = trigger_people_job_workflow(
                request_id=request_id,
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                name=request.name,
                url=request.url,
            )
        except Exception as e:
            print(f"Error triggering people job: {e}")
            return {"status": "error"}, 500

        return CreateJobResponse(
            request_id=request_id,
            status="pending"
        )
    
    @router.post(
        "/people/register",
        summary="Register a new job",
        description="Register a new job in the system.",
        include_in_schema=False, # Internally called by every civicpatch server
    )
    async def register_people_job_endpoint(
        request: CreatePeopleRegisterJobRequest,
        user: Identity = Depends(get_user)
    ):
        print(f"Registering job: {request.request_id} by user {user.provider_user_id} from provider {user.provider}")
        response = await register_job(
            requested_by_provider=user.provider,
            requested_by_provider_user_id=user.provider_user_id,
            request_id=request.request_id,
            job_type="people",
            arguments_json=request.arguments,
            server_source=request.server_source or None
        )
        return {"request_id": request.request_id, "status": "pending"}

    @router.post(
        "/people/{request_id}/result",
        include_in_schema=False, # Internally called by every civicpatch server
    )
    async def post_job_result_endpoint(
        request_id: str,
        request: PostJobResultRequest
    ):
        serialized_result = request.data
        await update_job_result(request_id, serialized_result)
        return {"request_id": request_id}


    @router.delete(
        "/people/{request_id}",
        summary="Cancel a job",
        description="Stop a specific job by its request ID.",
        response_model=DeleteJobResponse
    )
    async def stop_job_endpoint(request_id: str):
        # Implementation to stop a job
        # TBD
        return {"request_id": request_id, "status": "stopped"}

    return router