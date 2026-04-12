import asyncio
import json
import logging
import math
import os
import time
from typing import Any, Literal, Optional

import shared.utils.data_path_utils as data_path_utils
import shared.utils.id_utils
from shared.utils.statuses import JobStatus, PullRequestStatus
import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import job_service.people_collector.people_data_utils as people_data_utils
import services.github.github_api_service as github_service
import services.pipeline.candidate_service as candidate_service
import services.storage_service as storage_service
import services.temporal_service as temporal_service
import utils.file_utils
import database.jobs
from database.database import (
    get_job,
    get_job_result,
    get_job_data_json,
    get_job_status,
    get_job_github_run_id,
    get_jobs_with_errors,
    get_review_issues_page,
    get_active_jobs,
    get_unrecognized_roles_grouped,
    resolve_unrecognized_role_group,
    update_job_pull_request_url,
    update_job_pull_request_status,
    update_job_data,
    update_job_status,
    set_job_github_run_id,
)
from database.requests import register_request_with_job
from job_service.people_collector import people_collector
from schemas.common import Identity, Jurisdiction, Role, RouteCategory
from schemas.requests import HandleSubmitJobArtifactsRequest, ServerDetail
from services import pubsub_service
from utils.auth_utils import require_route_access

logger = logging.getLogger(__name__)

_is_production = os.getenv("APP_ENVIRONMENT", "").lower() == "production"

ARTIFACTS_BASE_URL = "https://civicpatch-artifacts.civicpatch.org"
PAUSED_CONTEXT_BUCKET = "civicpatch-artifacts"


async def update_and_publish(request_id: str, status: str, progress: Optional[int], jurisdiction_ocdid: Optional[str]):
    await update_job_status(request_id=request_id, status=status, progress=progress)
    if not jurisdiction_ocdid:
        job = await get_job(request_id)
        jurisdiction_ocdid = (job.get("arguments_json") or {}).get("jurisdiction_ocdid") if job else None
    if jurisdiction_ocdid:
        await pubsub_service.publish(
            f"job_status:{jurisdiction_ocdid}",
            json.dumps({"request_id": request_id, "status": status, "progress": progress}),
        )


class CreateJobRequest(BaseModel):
    jurisdiction_ocdid: str
    dispatch_mode: Literal["local", "remote"] = "remote"
    name: Optional[str] = None
    url: Optional[str] = None
    source_urls: Optional[list[str]] = None


class BatchJobRequest(BaseModel):
    state: str
    num_jurisdictions: int = 10


class RegisterGithubRunRequest(BaseModel):
    run_id: int


class UpdateJobStatusRequest(BaseModel):
    status: str
    progress: Optional[int] = None
    jurisdiction_ocdid: Optional[str] = None


class UpdateJobStatusResponse(BaseModel):
    request_id: str
    status: str
    progress: Optional[int] = None


class PostJobResultRequest(BaseModel):
    pull_request_url: Optional[str] = None
    data: Optional[Any] = None


class ResolveUnrecognizedRoleGroupRequest(BaseModel):
    role: str
    request_ids: list[str]


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
    pull_request_url: Optional[str] = None
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
            require_route_access(RouteCategory.TEAM_REQUIRED, ["maintainers"])
        ),
    ):
        if _is_production and request.dispatch_mode == "local":
            return JSONResponse(
                content=ErrorResponse(error="Local dispatch is not available in production").model_dump(),
                status_code=400,
            )

        try:
            request_id = shared.utils.id_utils.make_request_id()
            await register_request_with_job(
                request_id=request_id,
                job_type="people",
                arguments_json={
                    "jurisdiction_ocdid": request.jurisdiction_ocdid,
                    "name": request.name,
                    "url": request.url,
                    "source_urls": request.source_urls,
                },
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                requested_by_user_id=user.user_id,
            )
            await temporal_service.start_people_collector_workflow(
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                request_id=request_id,
                dispatch_mode=request.dispatch_mode,
                url=request.url,
                source_urls=request.source_urls,
            )
        except Exception as e:
            logger.exception(f"Error creating job: {e}")
            return JSONResponse(
                content=ErrorResponse(
                    error="Failed to start people collector workflow"
                ).model_dump(),
                status_code=500,
            )

        return CreateJobResponse(request_id=request_id, status=JobStatus.PENDING)

    @router.post("/batch", summary="Register and start a batch scrape job for a state")
    async def create_batch_jobs_endpoint(
        request: BatchJobRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, ["maintainers"])
        ),
    ):
        try:
            candidates = await candidate_service.get_scrape_candidates(request.state, request.num_jurisdictions)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        items = []
        for candidate in candidates:
            request_id = shared.utils.id_utils.make_request_id()
            await register_request_with_job(
                request_id=request_id,
                job_type="people",
                arguments_json={
                    "jurisdiction_ocdid": candidate.id,
                    "name": candidate.name,
                    "url": candidate.url,
                    "source_urls": None,
                },
                jurisdiction_ocdid=candidate.id,
                requested_by_user_id=user.user_id,
            )
            items.append({
                "jurisdiction_ocdid": candidate.id,
                "request_id": request_id,
                "name": candidate.name,
                "url": candidate.url,
            })

        await temporal_service.start_batch_people_collector_workflow(request.state, items)
        return {"jurisdictions": items}

    @router.post("/{request_id}/run", include_in_schema=False)
    async def register_github_run_endpoint(
        request_id: str,
        request: RegisterGithubRunRequest,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        updated = await set_job_github_run_id(request_id, request.run_id)
        if not updated:
            return JSONResponse(
                content=ErrorResponse(error="Job not found").model_dump(),
                status_code=404,
            )
        return {"request_id": request_id, "run_id": request.run_id}

    @router.get("/{request_id}/run", include_in_schema=False)
    async def get_github_run_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        run_id = await get_job_github_run_id(request_id)
        if run_id is None:
            return JSONResponse(content={"run_id": None}, status_code=404)
        return {"run_id": run_id}

    @router.get("/{request_id}/config", include_in_schema=False)
    async def get_job_config_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        job = await get_job(request_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        args = job.get("arguments_json") or {}
        return {"name": args.get("name"), "url": args.get("url"), "source_urls": args.get("source_urls")}

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
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])
        ),
    ):
        background_tasks.add_task(
            update_and_publish,
            request_id,
            request.status,
            request.progress,
            request.jurisdiction_ocdid,
        )

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
            tasks.append(("result", update_job_data(request_id, request.data)))
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
        job_status: Optional[str] = Form(None),
        _user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS])),
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
            job_status=job_status,
        )

        background_tasks.add_task(
            people_collector.handle_submit_job_artifacts,
            request=request_obj,
        )

        logger.info(
            f"[{request_id}] Total endpoint time: {time.time() - start_time:.3f}s"
        )
        return {"request_id": request_id, "status": "processing"}

    #@router.get(
    #    "/people/{request_id}",
    #    summary="Get job and job results, if available",
    #    description="Retrieve the status of a specific job by its request ID.",
    #    response_model=GetJobResponse,
    #    responses={404: {"model": ErrorResponse, "description": "Job not found"}},
    #)
    #async def get_job_endpoint(
    #    request_id: str,
    #    _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    #):
    #    job = await get_job(request_id)
    #    if job:
    #        return GetJobResponse(
    #            request_id=request_id,
    #            status=job["status"],
    #            progress=job["progress"],
    #            arguments=job["arguments_json"],
    #            result=job["data_json"],
    #            pull_request_url=job["pull_request_url"],
    #            created_at=job["created_at"],
    #            updated_at=job["updated_at"],
    #        )
    #    else:
    #        return JSONResponse(
    #            content=ErrorResponse(error="Job not found").model_dump(),
    #            status_code=404,
    #        )

    @router.post(
        "/{request_id}/resolve",
        summary="Manually resolve a job that is stuck in an error state",
    )
    async def resolve_job_endpoint(
        request_id: str,
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, ["admins"])),
    ):
        updated = await update_job_status(request_id=request_id, status=JobStatus.RESOLVED, progress=None)
        if not updated:
            return JSONResponse(
                content=ErrorResponse(error="Job not found").model_dump(),
                status_code=404,
            )

        async def _publish():
            job = await get_job(request_id)
            if job is None:
                return
            jurisdiction_ocdid = (job.get("arguments_json") or {}).get("jurisdiction_ocdid")
            if jurisdiction_ocdid:
                await pubsub_service.publish(
                    f"job_status:{jurisdiction_ocdid}",
                    json.dumps({"request_id": request_id, "status": JobStatus.RESOLVED, "progress": None}),
                )

        background_tasks.add_task(_publish)
        return {"request_id": request_id, "status": JobStatus.RESOLVED}

    @router.post(
        "/{request_id}/resume",
        summary="Resume a paused job",
        description="Send a human_approval signal to the Temporal workflow for this job.",
    )
    async def resume_job_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, ["maintainers"])),
    ):
        job = await get_job(request_id)
        if not job:
            return JSONResponse(
                content=ErrorResponse(error="Job not found").model_dump(),
                status_code=404,
            )
        jurisdiction_ocdid = (job.get("arguments_json") or {}).get("jurisdiction_ocdid")
        if not jurisdiction_ocdid:
            return JSONResponse(
                content=ErrorResponse(error="No jurisdiction_ocdid for job").model_dump(),
                status_code=422,
            )
        try:
            await temporal_service.signal_human_approval(jurisdiction_ocdid)
        except Exception as e:
            logger.exception(f"Error signalling human_approval: {e}")
            return JSONResponse(
                content=ErrorResponse(error="Failed to signal workflow").model_dump(),
                status_code=500,
            )
        return {"request_id": request_id, "status": "resumed"}

    @router.post(
        "/{request_id}/cancel",
        summary="Cancel a running job",
        description="Cancel the Temporal workflow for this job.",
    )
    async def cancel_job_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, ["admins"])),
    ):
        job = await get_job(request_id)
        if not job:
            return JSONResponse(
                content=ErrorResponse(error="Job not found").model_dump(),
                status_code=404,
            )
        jurisdiction_ocdid = (job.get("arguments_json") or {}).get("jurisdiction_ocdid")
        if not jurisdiction_ocdid:
            return JSONResponse(
                content=ErrorResponse(error="No jurisdiction_ocdid for job").model_dump(),
                status_code=422,
            )
        try:
            await temporal_service.cancel_workflow(jurisdiction_ocdid)
        except Exception as e:
            logger.exception(f"Error cancelling workflow: {e}")
            return JSONResponse(
                content=ErrorResponse(error="Failed to cancel workflow").model_dump(),
                status_code=500,
            )
        await update_job_status(request_id=request_id, status=JobStatus.CANCELLED, progress=None)
        return {"request_id": request_id, "status": JobStatus.CANCELLED}

    @router.get(
        "/active",
        summary="List currently active (non-terminal) jobs, optionally filtered by state",
    )
    async def get_active_jobs_endpoint(
        state_code: Optional[str] = None,
        page: int = 1,
        per_page: int = 25,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.CONTRIBUTORS])),
    ):
        jobs, total = await get_active_jobs(state_code=state_code, page=page, per_page=per_page)
        for job in jobs:
            job["jurisdiction_path"] = shared.utils.id_utils.jurisdiction_ocdid_to_folder(job["jurisdiction_ocdid"])
        return {"data": jobs, "total": total, "page": page, "per_page": per_page, "total_pages": math.ceil(total / per_page) if total else 1}

    @router.get(
        "/errors",
        summary="List jobs stuck in the pipeline with an error status",
    )
    async def get_jobs_with_errors_endpoint(
        state_code: Optional[str] = None,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])),
    ):
        jobs = await get_jobs_with_errors(state_code=state_code)

        for job in jobs:
            ocdid = job["jurisdiction_ocdid"]
            folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(ocdid)
            base = f"{ARTIFACTS_BASE_URL}/{job['request_id']}/data_source/{folder}"
            job["workflow_log_url"] = f"{base}/workflow.log"
            job["workflow_context_url"] = f"{base}/workflow_context.json"
            # TODO: move Cloudflare account ID to env var
            job["debug_url"] = f"https://dash.cloudflare.com/c9ae2b352766fe3e6f7dbee61bcd4c7c/r2/default/buckets/civicpatch-artifacts?prefix={job['request_id']}%2F"
            job["jurisdiction_path"] = folder

        return {"data": jobs}

    @router.get(
        "/events",
        summary="List review issues (unrecognized roles, dead URLs, etc.) with pagination",
    )
    async def get_job_events_endpoint(
        tags: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = "desc",
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])),
    ):
        issue_types = [t.strip() for t in tags.split(",")] if tags else []
        sort_desc = sort != "asc"
        rows, total = await get_review_issues_page(issue_types, page, per_page, sort_desc)
        return {"data": rows, "total": total}

    @router.get(
        "/unrecognized-roles/grouped",
        summary="List unrecognized roles grouped by role text, each with affected request IDs",
    )
    async def get_unrecognized_roles_grouped_endpoint(
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])),
    ):
        rows = await get_unrecognized_roles_grouped()
        return {"data": rows}

    @router.post(
        "/unrecognized-roles/grouped/resolve",
        summary="Bulk-resolve review session entries for a grouped unrecognized role",
    )
    async def resolve_unrecognized_roles_grouped_endpoint(
        body: ResolveUnrecognizedRoleGroupRequest,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])),
    ):
        await resolve_unrecognized_role_group(body.request_ids)
        return {"data": None}

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

    #@router.get("/people/pull_request/{branch_name}/data", include_in_schema=False)
    #async def get_job_pull_request_data_endpoint(
    #    branch_name: str,
    #    jurisdiction_ocdid: str,
    #    _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    #):
    #    request_id = branch_name.split("-")[-1]
    #    result = await get_job_result(request_id)

    #    return {
    #        "branch_name": branch_name,
    #        "data": result["data"] if result else None,
    #        "review_json": result["review_json"] if result else {},
    #    }

    # -- Jobs: List Jobs where the pull requests have duplicate jurisdictions ───────────
    @router.get(
        "/duplicates",
        summary="List jobs where the pull requests have duplicate jurisdictions",
    )
    async def list_jobs_with_duplicate_jurisdictions_endpoint(
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        jurisdiction_ocdids = await database.jobs.get_duplicate_jurisdiction_ocdids()
        return {"data": list(jurisdiction_ocdids)}

    @router.post(
        "/duplicates/close-stale",
        summary="Close all but the latest open PR for each duplicate jurisdiction",
    )
    async def close_stale_duplicate_prs_endpoint(
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS])
        ),
    ):
        stale = await database.jobs.get_stale_duplicate_pr_info()
        closed, failed = [], []
        for item in stale:
            success = await github_service.close_pull_request(str(item["pr_number"]))
            if success:
                await update_job_pull_request_status(item["request_id"], PullRequestStatus.CLOSED)
                closed.append(item["request_id"])
            else:
                failed.append(item["request_id"])
        return {"closed": closed, "failed": failed}

    @router.get(
        "/{request_id}/context/upload-url",
        summary="Get a presigned PUT URL for uploading paused workflow context",
        include_in_schema=False,
    )
    async def get_context_upload_url_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{request_id}/paused_context.json"
        url = storage_service.get_presigned_put_url(PAUSED_CONTEXT_BUCKET, key)
        return {"url": url}

    @router.get(
        "/{request_id}/context/download-url",
        summary="Get a presigned GET URL for downloading paused workflow context",
        include_in_schema=False,
    )
    async def get_context_download_url_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{request_id}/paused_context.json"
        url = storage_service.get_presigned_url_cached(PAUSED_CONTEXT_BUCKET, key)
        return {"url": url}

    @router.delete(
        "/{request_id}/context",
        summary="Delete paused workflow context from storage",
        include_in_schema=False,
    )
    async def delete_context_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{request_id}/paused_context.json"
        storage_service.delete_object(PAUSED_CONTEXT_BUCKET, key)
        return {"request_id": request_id}

    return router
