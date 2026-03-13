import asyncio
import json
import logging
import time
from typing import Any, Optional

import shared.utils.data_path_utils as data_path_utils
import shared.utils.id_utils
import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import job_service.people_collector.people_data_utils as people_data_utils
import services.github_service as github_service
import utils.file_utils
from database.database import (
    get_job,
    get_job_status,
    register_job,
    update_job_pull_request_url,
    update_job_result,
    update_job_status,
)
from job_service.people_collector import people_collector
from schemas.common import Identity, RouteCategory
from schemas.requests import HandleSubmitJobArtifactsRequest, ServerDetail
from services import pubsub_service
from utils.auth_utils import require_route_access

logger = logging.getLogger(__name__)


class CreateJobRequest(BaseModel):
    jurisdiction_ocdid: str
    name: Optional[str] = None
    url: str


class CreateRegisterJobRequest(BaseModel):
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


class PostJobResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class CreateJobResponse(BaseModel):
    request_id: str
    status: str


class GetJobResponse(BaseModel):
    request_id: str
    status: str
    progress: int
    arguments: dict
    result: Optional[Any] = None
    pull_request_url: Optional[str] = None  # TODO: implement
    created_at: float
    updated_at: float


class GetJobStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: int


class ErrorResponse(BaseModel):
    error: str


def get_router(api_key_header):
    router = APIRouter()

    @router.post(
        "",
        summary="Trigger scrape people job",
        description="Trigger a new scrape people job.",
        response_model=CreateJobResponse,
        responses={
            429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
            500: {"model": ErrorResponse, "description": "Internal server error"},
        },
    )
    async def create_people_job_endpoint(
        request: CreateJobRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.SERVICE, ["default"])
        ),
    ):
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
                content=ErrorResponse(
                    error="Failed to trigger people job with GitHub"
                ).model_dump(),
                status_code=500,
            )

        return CreateJobResponse(request_id=request_id, status="pending")

    @router.post(
        "/register",
        summary="Register a new job",
        description="Register a new job in the system.",
        include_in_schema=False,
    )
    async def register_people_job_endpoint(
        request: CreateRegisterJobRequest,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        print(
            f"Registering job: {request.request_id} by user {user.provider_user_id} from provider {user.provider}"
        )
        _response = await register_job(
            requested_by_provider=user.provider,
            requested_by_provider_user_id=user.provider_user_id,
            request_id=request.request_id,
            job_type="people",
            arguments_json=request.arguments,
            server_source=request.server_source or None,
        )
        return {"request_id": request.request_id, "status": "pending"}

    # ── Jobs: Status & Progress ──────────────

    @router.patch(
        "/{request_id}/status",
        summary="Update job status and progress",
        description="Update status and/or progress of a specific job by its request ID.",
        include_in_schema=False,
    )
    async def patch_job_status_endpoint(
        request_id: str,
        request: UpdateJobStatusRequest,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.SERVICE, ["default"])
        ),
    ):
        async def _update_and_publish():
            await update_job_status(
                request_id=request_id, status=request.status, progress=request.progress
            )
            key = f"people:{request.jurisdiction_ocdid}"
            await pubsub_service.publish(
                key,
                json.dumps(
                    {
                        "request_id": request_id,
                        "status": request.status,
                        "progress": request.progress,
                    }
                ),
            )

        background_tasks.add_task(_update_and_publish)

        return UpdateJobStatusResponse(
            request_id=request_id, status=request.status, progress=request.progress
        )

    # ── Jobs: Submit & Results ───────────────

    @router.post(
        "/{request_id}/result",
        include_in_schema=False,
    )
    async def post_job_result_endpoint(
        request_id: str,
        request: PostJobResultRequest,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        errors = []

        tasks = []
        if request.data:  # Called from within civicpatch project
            tasks.append(("result", update_job_result(request_id, request.data)))
        if request.pull_request_url:  # Called from open-data repo
            tasks.append(
                (
                    "pull_request",
                    update_job_pull_request_url(
                        request_id, pull_request_url=request.pull_request_url
                    ),
                )
            )

        if tasks:
            results = await asyncio.gather(
                *[t[1] for t in tasks], return_exceptions=True
            )
            for (label, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    errors.append(f"Failed to update {label}: {result}")
                elif not result:
                    errors.append(f"Failed to update {label}, job may not exist")

        return {"request_id": request_id, "errors": errors}

    @router.post(
        "/{request_id}/submit",
        summary="Upload zip file containing municipal data",
        description="Accepts a zip file containing municipal data and processes it",
        include_in_schema=False,
    )
    async def submit_people_endpoint(
        request_id: str,
        file: UploadFile,
        background_tasks: BackgroundTasks,
        jurisdiction_ocdid: str = Form(...),
        _user: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        start_time = time.time()

        if not file.filename:
            raise HTTPException(status_code=400, detail="No file name available")

        if not file.filename.lower().endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only .zip files are accepted")
        if file.content_type not in ["application/zip", "application/x-zip-compressed"]:
            raise HTTPException(
                status_code=400, detail="Invalid content type for zip file"
            )

        logger.info(f"Processing intake for {request_id} - {jurisdiction_ocdid}")

        file_path, temp_dir = await utils.file_utils.save_upload_to_temp(file)

        request_obj = HandleSubmitJobArtifactsRequest(
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            server_detail=ServerDetail(
                user_email="jobs-people@civicpatch.org", server_url="civicpatch.org"
            ),
            zip_path=file_path,
            temp_dir=temp_dir,
        )

        background_tasks.add_task(
            people_collector.handle_submit_job_artifacts,
            request=request_obj,
        )

        logger.info(
            f"[{request_id}] Total endpoint time: {time.time() - start_time:.3f}s"
        )
        return {"request_id": request_id, "status": "processing"}

    @router.get(
        "/people/{request_id}",
        summary="Get job and job results, if available",
        description="Retrieve the status of a specific job by its request ID.",
        response_model=GetJobResponse,
        responses={404: {"model": ErrorResponse, "description": "Job not found"}},
    )
    async def get_job_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        job = await get_job(request_id)
        if job:
            return GetJobResponse(
                request_id=request_id,
                status=job["status"],
                progress=job["progress"],
                arguments=job["arguments_json"],
                result=job["result_json"],
                pull_request_url=job["pull_request_url"],
                created_at=job["created_at"],
                updated_at=job["updated_at"],
            )
        else:
            return JSONResponse(
                content=ErrorResponse(error="Job not found").model_dump(),
                status_code=404,
            )

    @router.get(
        "/{request_id}/status",
        summary="Get job status and progress",
        description="Retrieve the progress of a specific job by its request ID.",
        response_model=GetJobStatusResponse,
        responses={404: {"model": ErrorResponse, "description": "Job not found"}},
    )
    async def get_job_status_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        response = await get_job_status(request_id)
        if not response:
            return JSONResponse(
                content=ErrorResponse(error="Job not found").model_dump(),
                status_code=404,
            )

        return GetJobStatusResponse(
            request_id=request_id,
            status=response["status"],
            progress=response["progress"],
        )

    @router.get("/people/pull_request/open", include_in_schema=False)
    async def get_open_people_pull_requests_endpoint(
        jurisdiction_ocdid: Optional[str] = None,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        branch_name_suffix = shared.utils.id_utils.jurisdiction_ocdid_to_slug(
            jurisdiction_ocdid
        )
        open_pull_requests = (
            await github_service.get_open_pull_request_by_branch_suffix(
                branch_name_suffix
            )
        )
        return {"data": open_pull_requests}

    @router.get("/people/pull_request/{branch_name}/data", include_in_schema=False)
    async def get_job_pull_request_data_endpoint(
        branch_name: str,
        jurisdiction_ocdid: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        file_path = data_path_utils.get_data_file_path(jurisdiction_ocdid)
        context_file_path = data_path_utils.get_data_source_context_file_path(
            jurisdiction_ocdid
        )
        # Chop off leading "/app/" from file_path
        if file_path.startswith("/app/"):
            file_path = file_path[len("/app/") :]

        data_github_response = await github_service.get_github_file_contents(
            github_file_path=file_path, ref=branch_name
        )

        context_github_response = await github_service.get_github_file_contents(
            github_file_path=context_file_path, ref=branch_name
        )
        if context_github_response:
            context = json.loads(context_github_response)
            review = None
            try:
                people = (
                    data_github_response and yaml.safe_load(data_github_response) or []
                )
                review = people_data_utils.extract_review_data(context, people)
            except Exception as e:
                print("Error extracting review data, skipping:", e)

        if data_github_response is None:
            return {"branch_name": branch_name, "data": None}

        response = (
            yaml.safe_load(data_github_response) if data_github_response else None
        )

        return {"branch_name": branch_name, "data": response, "review": review or None}

    return router
