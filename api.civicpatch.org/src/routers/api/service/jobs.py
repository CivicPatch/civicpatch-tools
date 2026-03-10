from fastapi import APIRouter, Depends, Form, HTTPException, Security, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse
import services.storage_service as storage_service
from services.api_service import can_make_api_request, can_call_request_id
from database import (
    update_job_status,
    register_job,
    update_job_result,
    update_job_pull_request_url
)    
from utils.auth_utils import get_user, require_route_access
from services import pubsub_service
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from schemas.common import RouteCategory
from schemas.common import Identity
import shared.utils.id_utils
import shared.utils.data_path_utils as data_path_utils
import services.github_service as github_service
import json
from job_service.people_collector import people_collector
from schemas.requests import HandleSubmitJobArtifactsRequest, ServerDetail
import asyncio
import utils.file_utils
import time

import logging
logger = logging.getLogger(__name__)

class CreateJobResponse(BaseModel):
    request_id: str
    status: str

class CreatePeopleRegisterJobRequest(BaseModel):
    request_id: str
    arguments: dict
    server_source: Optional[str] = None

class UpdateJobStatusRequest(BaseModel):
    status: str
    progress: Optional[int]
    jurisdiction_ocdid: str

class UpdateJobStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: Optional[int] = None

class ErrorResponse(BaseModel):
    error: str

class PostJobResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None

class PostJobPullRequestDataRequest(BaseModel):
    jurisdiction_ocdid: str
    data: List[Dict[str, Any]]

class DeleteJobResponse(BaseModel):
    request_id: str
    status: str

def get_router(api_key_header):
    router = APIRouter()

    @router.patch(
        "/people/{request_id}/status",
        summary="Update job status and progress",
        description="Update status and/or progress of a specific job by its request ID.",
        include_in_schema=False
    )
    async def patch_job_status_endpoint(
        request_id: str,
        request: UpdateJobStatusRequest,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE, ["default"]))
    ):
        #can_call_request_id_response = await can_call_request_id(user, request_id)
        #if not can_call_request_id_response:
        #    return JSONResponse(
        #        content=ErrorResponse(error="Not authorized to update status for this request ID: " + request_id).model_dump(),
        #        status_code=403
        #    )

        async def _update_and_publish():
            await update_job_status(
                request_id=request_id,
                status=request.status,
                progress=request.progress
            )
            key = f"people:{request.jurisdiction_ocdid}"
            await pubsub_service.publish(key, json.dumps({
                "request_id": request_id,
                "status": request.status,
                "progress": request.progress
            }))

        background_tasks.add_task(_update_and_publish)

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
        responses={
            429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
            500: {"model": ErrorResponse, "description": "Internal server error"}
        }
    )
    async def create_people_job_endpoint(
        request: CreatePeopleJobRequest,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE, ["default"]))
    ):
        #api_request_allowed, reason = await can_make_api_request(user.provider, user.provider_user_id)
        #if not api_request_allowed:
        #    return JSONResponse(
        #        content=ErrorResponse(error=reason).model_dump(),
        #        status_code=429
        #    )

        try:
            request_id = shared.utils.id_utils.make_request_id() 
            _response = await github_service.trigger_people_job_workflow(
                request_id=request_id,
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                name=request.name,
                url=request.url,
            )
        except Exception as e:
            print(f"Error triggering people job with GitHub: {e}")
            return JSONResponse(
                content=ErrorResponse(error="Failed to trigger people job with GitHub").model_dump(),
                status_code=500
            )

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
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE))
    ):
        print(f"Registering job: {request.request_id} by user {user.provider_user_id} from provider {user.provider}")
        _response = await register_job(
            requested_by_provider=user.provider,
            requested_by_provider_user_id=user.provider_user_id,
            request_id=request.request_id,
            job_type="people",
            arguments_json=request.arguments,
            server_source=request.server_source or None
        )
        return {"request_id": request.request_id, "status": "pending"}

    # TODO: maybe want to get rid of result
    @router.post(
        "/people/{request_id}/submit",
        summary="Upload zip file containing municipal data",
        description="Accepts a zip file containing municipal data and processes it",
        include_in_schema=False,
    )
    async def submit_people_endpoint(
        request_id: str,
        file: UploadFile,
        background_tasks: BackgroundTasks,
        jurisdiction_ocdid: str = Form(...),
        _user: Identity = Depends(require_route_access(RouteCategory.SERVICE))
    ):
        start_time = time.time()

        # Check file type
        if not file.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only .zip files are accepted")
        if file.content_type not in ["application/zip", "application/x-zip-compressed"]:
            raise HTTPException(
                status_code=400, detail="Invalid content type for zip file"
            )

        logger.info(f"Processing intake for {request_id} - {jurisdiction_ocdid}")

        log_step = lambda msg: logger.info(f"[{request_id}] {msg}: {time.time() - start_time:.3f}s elapsed")

        log_step("Start file save")
        file_path, temp_dir = await utils.file_utils.save_upload_to_temp(file)
        log_step("File saved to disk")

        request_obj = HandleSubmitJobArtifactsRequest(
            file_path=file_path,  # Pass the path, not the UploadFile
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            server_detail=ServerDetail(
                user_email="jobs-people@civicpatch.org",
                server_url="civicpatch.org"
            ),
            zip_path=file_path,
            temp_dir=temp_dir
        )

        log_step("Before background task add")
        background_tasks.add_task(
            people_collector.handle_submit_job_artifacts,
            request=request_obj,
        )
        log_step("Background task added")

        logger.info(f"[{request_id}] Total endpoint time: {time.time() - start_time:.3f}s")
        return {"request_id": request_id, "status": "processing"}


    @router.post(
        "/people/{request_id}/result",
        include_in_schema=False,
    )
    async def post_job_result_endpoint(
        request_id: str,
        request: PostJobResultRequest,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE))
    ):
        errors = []
        #can_call_request_id_response = await can_call_request_id(user, request_id)
        #if not can_call_request_id_response:
        #    return JSONResponse(
        #        content=ErrorResponse(error="Not authorized to post result for this request ID: " + request_id).model_dump(),
        #        status_code=403
        #    )

        tasks = []
        if request.data:
            tasks.append(("result", update_job_result(request_id, request.data)))
        if request.pull_request_url:
            tasks.append(("pull_request", update_job_pull_request_url(request_id, pull_request_url=request.pull_request_url)))

        if tasks:
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for (label, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    errors.append(f"Failed to update {label}: {result}")
                elif not result:
                    errors.append(f"Failed to update {label}, job may not exist")

        return {"request_id": request_id, "errors": errors}

    @router.post(
        "/people/pull_request/{branch_name}/data",
        include_in_schema=False
    )
    async def post_job_pull_request_data_endpoint(
        branch_name: str,
        request: PostJobPullRequestDataRequest,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        print("branch_name", branch_name)
        user_name = user.email
        file_path = data_path_utils.get_data_file_path(request.jurisdiction_ocdid)
        # Chop off leading "/app/" from file_path
        if file_path.startswith("/app/"):
            file_path = file_path[len("/app/"):]
        _github_response = await github_service.update_pull_request_file(
            branch_name=branch_name,
            file_path=file_path,
            new_data=request.data,
            commit_message=f"Data update by {user_name}"
        )
        if not _github_response:
            return JSONResponse(
                content=ErrorResponse(error="Failed to update pull request data on GitHub").model_dump(),
                status_code=500
            )
        return {"branch_name": branch_name, "status": "success"}

    @router.delete(
        "/people/{request_id}",
        summary="Cancel a job",
        description="Stop a specific job by its request ID.",
        response_model=DeleteJobResponse
    )
    async def stop_job_endpoint(request_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE))
    ):
        # Implementation to stop a job
        # TBD
        return {"request_id": request_id, "status": "stopped"}
    
    return router