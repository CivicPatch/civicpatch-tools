from fastapi import APIRouter, Depends 
from fastapi.responses import JSONResponse
from typing import Optional, Any, List, Dict
from pydantic import BaseModel
from schemas.common import Identity
import services.github_service as github_service
from database import (
    get_job,
    get_job_status,
)
import database as database
from utils.auth_utils import get_user, require_route_access
import shared.utils.data_path_utils as data_path_utils
import shared.utils.id_utils
import job_service.people_collector.people_data_utils as people_data_utils
import json
import yaml
from schemas.common import RouteCategory

import logging

class GetJobResponse(BaseModel):
    request_id: str
    status: str
    progress: int
    arguments: dict
    result: Optional[Any] = None
    pull_request_url: Optional[str] = None # TODO: implement
    created_at: float
    updated_at: float

class GetJobStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: int

class ErrorResponse(BaseModel):
    error: str

logger = logging.getLogger(__name__)

def get_router(api_key_header):
    router = APIRouter()

    @router.get(
        "/people/pull_requests",
        include_in_schema=False
    )
    async def get_people_pull_requests_endpoint(
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        open_pull_requests = await github_service.get_open_pull_requests()
        print("open_pull_requests", open_pull_requests)
        return {"data": open_pull_requests}

    @router.get(
        "/people/{request_id}",
        summary="Get job and job results, if available",
        description="Retrieve the status of a specific job by its request ID.",
        response_model=GetJobResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Job not found"}
        }
    )
    async def get_job_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        job = await get_job(request_id)
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
        response_model=GetJobStatusResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Job not found"}
        }
    )
    async def get_job_status_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        response = await get_job_status(request_id)
        if not response:
            return JSONResponse(
                content=ErrorResponse(error="Job not found").model_dump(),
                status_code=404
            )

        return GetJobStatusResponse(
            request_id=request_id,
            status=response['status'],
            progress=response['progress']
        )

    @router.get(
        "/people/pull_request/open",
        include_in_schema=False
    )
    async def get_open_people_pull_requests_endpoint(
        jurisdiction_ocdid: Optional[str] = None,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        branch_name_suffix = shared.utils.id_utils.jurisdiction_ocdid_to_slug(jurisdiction_ocdid)
        open_pull_requests = await github_service.get_open_pull_request_by_branch_suffix(branch_name_suffix)
        return {"data": open_pull_requests}

    @router.get(
        "/people/pull_request/{branch_name}/data",
        include_in_schema=False
    )
    async def get_job_pull_request_data_endpoint(
        branch_name: str,
        jurisdiction_ocdid: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        file_path = data_path_utils.get_data_file_path(jurisdiction_ocdid)
        context_file_path = data_path_utils.get_data_source_context_file_path(jurisdiction_ocdid)
        # Chop off leading "/app/" from file_path
        if file_path.startswith("/app/"):
            file_path = file_path[len("/app/"):]

        data_github_response = await github_service.get_github_file_contents(
            github_file_path=file_path,
            ref=branch_name
        )
        
        context_github_response = await github_service.get_github_file_contents(
            github_file_path=context_file_path,
            ref=branch_name
        )
        if context_github_response:
            context = json.loads(context_github_response)
            review = None
            try:
                people = data_github_response and yaml.safe_load(data_github_response) or []
                review = people_data_utils.extract_review_data(context, people)
            except Exception as e:
                print("Error extracting review data, skipping:", e)

        if data_github_response is None:
            return {"branch_name": branch_name, "data": None}

        response = yaml.safe_load(data_github_response) if data_github_response else None

        return {
            "branch_name": branch_name, 
            "data": response, 
            "review": review or None
        }

    return router