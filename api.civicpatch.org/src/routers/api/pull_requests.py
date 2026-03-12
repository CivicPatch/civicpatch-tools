from fastapi import APIRouter, Depends, Form, HTTPException, Security, UploadFile, BackgroundTasks, Body
from fastapi.responses import JSONResponse
import services.storage_service as storage_service
from services.api_service import can_make_api_request, can_call_request_id
from utils.auth_utils import get_user, require_route_access
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from schemas.common import RouteCategory
from schemas.common import Identity
import shared.utils.id_utils
import services.github_service as github_service
import database.people
import asyncio
import time

import logging
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────

class PostJobPullRequestDataRequest(BaseModel):
    jurisdiction_ocdid: str
    request_id: str
    data: List[Dict[str, Any]]

# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────

class DeleteJobResponse(BaseModel):
    request_id: str
    status: str

class ErrorResponse(BaseModel):
    error: str

# ──────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────

def get_router(api_key_header):
    router = APIRouter()

    # ── Pull Requests: List & Data ───────────
    @router.get(
        "/data",
        summary="Get YAML data from a pull request branch",
    )
    async def get_pull_request_data_endpoint(
        jurisdiction_ocdid: str,
        request_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, ["maintainers"]))
    ):
        file_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
        people_data = await database.people.get_people_by_jurisdiction_ocdids([jurisdiction_ocdid])

        file_content = await github_service.get_pull_request_file_yaml(
            jurisdiction_ocdid=jurisdiction_ocdid,
            request_id=request_id,
            file_path=f"data/{file_path}.yml"
        )
        if file_content is None:
            return JSONResponse(
                content={"error": "Data file not found on branch"},
                status_code=404
            )

        return {
            "request_id": request_id,
            "file_path": file_path,
            "data": {
                "existing": people_data ,
                "pull_request": file_content,
            }
        }

    # ── Pull Requests: Update Data ───────────

    @router.post(
        "/data",
        include_in_schema=False
    )
    async def post_job_pull_request_data_endpoint(
        request: PostJobPullRequestDataRequest,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        user_name = user.email
        file_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(request.jurisdiction_ocdid)
        branch_name = shared.utils.id_utils.make_git_branch(
            request.jurisdiction_ocdid, request.request_id
        )
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

    # ── Pull Requests: Batch Data ────────────

    @router.get(
        "/with-data",
        summary="Batch get pull request details and data",
    )
    async def get_pull_requests_with_data(
        page: int = 1,
        per_page: int = 10,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, ["maintainers"]))
    ):
        pull_requests = await github_service.get_open_pull_requests()
        total = len(pull_requests)
        total_pages = (total + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        paged_pull_requests = pull_requests[start:end]

        # 1. Collect all unique jurisdiction_ocdids
        jurisdiction_ocdids = list({pr.jurisdiction_ocdid for pr in paged_pull_requests})
        request_ids = list({pr.request_id for pr in paged_pull_requests})
        # 2. Fetch all people data in one call
        data = await database.people.get_pull_request_data_by_request_ids(jurisdiction_ocdids, request_ids)
        async def fetch_one(pr):
            request_id = pr.request_id
            return {
                "details": pr,
                "existing": data.get(request_id, {}).get("existing", []),
                "pull_request": data.get(request_id, {}).get("pull_request", []),
            }

        results = await asyncio.gather(*(fetch_one(pr) for pr in paged_pull_requests))
        return {
            "data": results,
            "total": total,
            "total_pages": total_pages,
            "page": page,
            "per_page": per_page,
        }

    # ── Jobs: Cancel ─────────────────────────

    # TBD: implement
    @router.delete(
        "/{request_id}",
        summary="Cancel a job",
        description="Stop a specific job by its request ID.",
        response_model=DeleteJobResponse
    )
    async def stop_job_endpoint(
        request_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE))
    ):
        # TBD
        return {"request_id": request_id, "status": "stopped"}
    
    return router