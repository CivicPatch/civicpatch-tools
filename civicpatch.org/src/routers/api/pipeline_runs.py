import asyncio
import json
import logging
import math
import os
import time
from typing import Optional
import shared.utils.data_path_utils as data_path_utils
import shared.utils.id_utils
from shared.utils.statuses import PipelineRunStatus, PullRequestStatus, TERMINAL_PIPELINE_RUN_STATUSES
import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

import lib.github.api as github_service
import core.jurisdiction_scrape_candidate as candidate_service
import lib.storage as storage_service
import lib.temporal.client as temporal_service
import lib.files as file_utils
import database.pipeline_runs
from database.pipeline_runs import (
    get_pipeline_run,
    get_pipeline_run_result,
    get_pipeline_run_data_json,
    get_pipeline_run_status,
    get_pipeline_run_github_run_id,
    get_active_pipeline_runs,
    update_pipeline_run_data,
    update_pipeline_run_status,
    set_pipeline_run_github_run_id,
)
from database.issues import (
    get_issues_page,
    get_issue_by_id,
    get_issue_counts,
    get_unrecognized_roles_grouped,
    resolve_unrecognized_role_group,
    resolve_issue,
    set_issue_flagged,
    upsert_issue,
    supersede_prior_jurisdiction_issues,
)
from database.pull_requests import (
    update_pipeline_run_pull_request_url,
    update_pull_request_status,
)
from database.requests import (
    register_request_with_pipeline_run,
    register_request_with_pipeline_run_if_not_exists,
    get_request_jurisdiction,
    get_issue_request_details,
)
from core import people_collector
from schemas.common import Identity, Jurisdiction, Role, RouteCategory, has_at_least
from schemas.pipeline_runs import (
    CreatePipelineRunRequest,
    BatchPipelineRunRequest,
    RegisterPipelineRunRequest,
    RegisterGithubRunRequest,
    UpdatePipelineRunStatusRequest,
    UpdatePipelineRunStatusResponse,
    PostPipelineRunResultRequest,
    ResolveUnrecognizedRoleGroupRequest,
    FlagPipelineIssueRequest,
    CreatePipelineRunResponse,
    GetPipelineRunResponse,
    GetPipelineRunStatusResponse,
    ErrorResponse,
)
from schemas.pipeline_runs import HandleSubmitPipelineRunArtifactsRequest, ServerDetail
import lib.pubsub as pubsub_service
from lib.auth import require_route_access

logger = logging.getLogger(__name__)

_is_production = os.getenv("APP_ENVIRONMENT", "").lower() == "production"


ARTIFACTS_BASE_URL = "https://civicpatch-artifacts.civicpatch.org"
PAUSED_CONTEXT_BUCKET = "civicpatch-artifacts"


def _build_request_row(r: dict, issue_type: str, issue_key: str) -> dict:
    args = r.get("arguments_json") or {}
    url = args.get("url")
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(r["jurisdiction_ocdid"]) if r.get("jurisdiction_ocdid") else None
    if issue_type == "unrecognized_role":
        matching = [
            p for p in (r.get("data_json") or [])
            if isinstance(p, dict) and (p.get("office") or {}).get("name", "") == issue_key
        ]
        people = [{"name": p["name"]} for p in matching]
        source_urls = list({u for p in matching for u in (p.get("source_urls") or [])})
    else:
        people = []
        source_urls = [url] if url else []
    return {
        "request_id": r.get("request_id"),
        "jurisdiction_ocdid": r.get("jurisdiction_ocdid"),
        "jurisdiction_name": r.get("jurisdiction_name"),
        "jurisdiction_path": folder,
        "url": url,
        "source_urls": source_urls,
        "people": people,
    }


async def update_pipeline_run_and_publish(request_id: str, status: str, progress: Optional[int], jurisdiction_ocdid: Optional[str], error_type: Optional[str] = None, error_detail: Optional[dict] = None):
    await update_pipeline_run_status(request_id=request_id, status=status, progress=progress)
    
    if not jurisdiction_ocdid:
        pipeline_run = await get_pipeline_run(request_id)
        jurisdiction_ocdid = (pipeline_run.get("arguments_json") or {}).get("jurisdiction_ocdid") if pipeline_run else None
    if jurisdiction_ocdid:
        if status in TERMINAL_PIPELINE_RUN_STATUSES:
            await supersede_prior_jurisdiction_issues(jurisdiction_ocdid, request_id)
        await pubsub_service.publish(
            f"job_status:{jurisdiction_ocdid}",
            json.dumps({"request_id": request_id, "status": status, "progress": progress}),
        )


async def _register_pipeline_run_bg(request: RegisterPipelineRunRequest) -> None:
    try:
        await register_request_with_pipeline_run_if_not_exists(
            request_id=request.request_id,
            job_type="people",
            arguments_json={
                "jurisdiction_ocdid": request.jurisdiction_ocdid,
                "name": request.name,
                "url": request.url,
                "source_urls": None,
            },
            jurisdiction_ocdid=request.jurisdiction_ocdid,
        )
    except Exception:
        logger.exception(f"[{request.request_id}] Failed to register pipeline run in background")


def get_router(api_key_header):
    router = APIRouter()

    @router.post(
        "",
        summary="Trigger a people collector pipeline run",
        description="Trigger a new people collector pipeline run.",
        response_model=CreatePipelineRunResponse,
        responses={
            429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
            500: {"model": ErrorResponse, "description": "Internal server error"},
        },
    )
    async def create_people_pipeline_run_endpoint(
        request: CreatePipelineRunRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)
        ),
    ):
        if _is_production and request.dispatch_mode == "local":
            return JSONResponse(
                content=ErrorResponse(error="Local dispatch is not available in production").model_dump(),
                status_code=400,
            )

        try:
            request_id = shared.utils.id_utils.make_request_id()
            await register_request_with_pipeline_run(
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
            logger.exception(f"Error creating pipeline run: {e}")
            return JSONResponse(
                content=ErrorResponse(
                    error="Failed to start people collector workflow"
                ).model_dump(),
                status_code=500,
            )

        return CreatePipelineRunResponse(request_id=request_id, status=PipelineRunStatus.PENDING)

    @router.post("/batch", summary="Register and start a batch pipeline run for a state")
    async def create_batch_pipeline_runs_endpoint(
        request: BatchPipelineRunRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)
        ),
    ):
        try:
            candidates = await candidate_service.get_scrape_candidates(request.state, request.num_jurisdictions)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

        items = []
        for candidate in candidates:
            request_id = shared.utils.id_utils.make_request_id()
            await register_request_with_pipeline_run(
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

    @router.post("/register", include_in_schema=False)
    async def register_pipeline_run_endpoint(
        request: RegisterPipelineRunRequest,
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        background_tasks.add_task(_register_pipeline_run_bg, request)
        return {"data": {"request_id": request.request_id}}

    @router.post("/{request_id}/run", include_in_schema=False)
    async def register_github_run_endpoint(
        request_id: str,
        request: RegisterGithubRunRequest,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        updated = await set_pipeline_run_github_run_id(request_id, request.run_id)
        if not updated:
            return JSONResponse(
                content=ErrorResponse(error="Pipeline run not found").model_dump(),
                status_code=404,
            )
        return {"request_id": request_id, "run_id": request.run_id}

    @router.get("/{request_id}/run", include_in_schema=False)
    async def get_github_run_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        run_id = await get_pipeline_run_github_run_id(request_id)
        if run_id is None:
            return JSONResponse(content={"run_id": None}, status_code=404)
        return {"run_id": run_id}

    @router.get("/{request_id}/config", include_in_schema=False)
    async def get_pipeline_run_config_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        pipeline_run = await get_pipeline_run(request_id)
        if not pipeline_run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        args = pipeline_run.get("arguments_json") or {}
        return {"name": args.get("name"), "url": args.get("url"), "source_urls": args.get("source_urls")}

    # ── Pipeline Runs: Status & Progress ──────────────

    @router.patch(
        "/{request_id}/status",
        summary="Update pipeline run status and progress",
        description="Update status and/or progress of a specific pipeline run by its request ID.",
        include_in_schema=False,
    )
    async def patch_pipeline_run_status_endpoint(
        request_id: str,
        request: UpdatePipelineRunStatusRequest,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)
        ),
    ):
        background_tasks.add_task(
            update_pipeline_run_and_publish,
            request_id,
            request.status,
            request.progress,
            request.jurisdiction_ocdid,
            request.error_type,
            request.error_detail,
        )

        return UpdatePipelineRunStatusResponse(
            request_id=request_id, status=request.status, progress=request.progress
        )

    # ── Pipeline Runs: Submit & Results ───────────────

    @router.post(
        "/{request_id}/result",
        include_in_schema=False,
    )
    async def post_pipeline_run_result_endpoint(
        request_id: str,
        request: PostPipelineRunResultRequest,
        user: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        errors = []

        tasks = []
        if request.data:  # Called from within civicpatch project
            tasks.append(("result", update_pipeline_run_data(request_id, request.data)))
        if request.pull_request_url:  # Called from open-data repo
            tasks.append(
                (
                    "pull_request",
                    update_pipeline_run_pull_request_url(
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
                    errors.append(f"Failed to update {label}, pipeline run may not exist")

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
        pipeline_run_status: Optional[str] = Form(None),
        env: str = Form("production"),
        _user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
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

        file_path, temp_dir = await file_utils.save_upload_to_temp(file)

        request_obj = HandleSubmitPipelineRunArtifactsRequest(
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            server_detail=ServerDetail(user_email="jobs-people@civicpatch.org"),
            zip_path=file_path,
            temp_dir=temp_dir,
            pipeline_run_status=pipeline_run_status,
            env=env,
        )

        background_tasks.add_task(
            people_collector.handle_submit_pipeline_run_artifacts,
            request=request_obj,
        )

        logger.info(
            f"[{request_id}] Total endpoint time: {time.time() - start_time:.3f}s"
        )
        return {"request_id": request_id, "status": "processing"}

    @router.post(
        "/{request_id}/cancel",
        summary="Cancel a running pipeline run",
        description="Cancel the Temporal workflow for this pipeline run.",
    )
    async def cancel_pipeline_run_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        pipeline_run = await get_pipeline_run(request_id)
        if not pipeline_run:
            return JSONResponse(
                content=ErrorResponse(error="Pipeline run not found").model_dump(),
                status_code=404,
            )
        jurisdiction_ocdid = (pipeline_run.get("arguments_json") or {}).get("jurisdiction_ocdid")
        if not jurisdiction_ocdid:
            return JSONResponse(
                content=ErrorResponse(error="No jurisdiction_ocdid for pipeline run").model_dump(),
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
        await update_pipeline_run_status(request_id=request_id, status=PipelineRunStatus.CANCELLED, progress=None)
        return {"request_id": request_id, "status": PipelineRunStatus.CANCELLED}

    @router.get(
        "/active",
        summary="List currently active (non-terminal) pipeline runs, optionally filtered by state",
    )
    async def get_active_pipeline_runs_endpoint(
        state_code: Optional[str] = None,
        page: int = 1,
        per_page: int = 25,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.CONTRIBUTORS)),
    ):
        pipeline_runs, total = await get_active_pipeline_runs(state_code=state_code, page=page, per_page=per_page)
        for run in pipeline_runs:
            run["jurisdiction_path"] = shared.utils.id_utils.jurisdiction_ocdid_to_folder(run["jurisdiction_ocdid"])
        return {"data": pipeline_runs, "total": total, "page": page, "per_page": per_page, "total_pages": math.ceil(total / per_page) if total else 1}

    @router.get("/issues/counts", summary="Count pending issues grouped by issue_type")
    async def get_issue_counts_endpoint(
        state_code: Optional[str] = None,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        counts = await get_issue_counts(state_code=state_code)
        return {"data": counts}

    @router.get(
        "/issues",
        summary="List review issues (unrecognized roles, dead URLs, etc.) with pagination",
    )
    async def get_review_issues_endpoint(
        tags: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = "desc",
        state_code: Optional[str] = None,
        show_archived: bool = False,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        issue_types = [t.strip() for t in tags.split(",")] if tags else []
        sort_desc = sort != "asc"
        rows, total = await get_issues_page(issue_types, page, per_page, sort_desc, state_code=state_code, show_archived=show_archived)
        return {"data": rows, "total": total}

    @router.post(
        "/issues/{issue_id}/resolve",
        summary="Mark a review issue as resolved",
    )
    async def resolve_review_issue_endpoint(
        issue_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        issue = await get_issue_by_id(issue_id)
        if issue is None:
            raise HTTPException(status_code=404)
        await resolve_issue(issue_id)
        return {"data": None}

    @router.post(
        "/issues/{issue_id}/dismiss",
        summary="Dismiss a review issue without opening a PR",
    )
    async def dismiss_review_issue_endpoint(
        issue_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        issue = await get_issue_by_id(issue_id)
        if issue is None:
            raise HTTPException(status_code=404)
        await resolve_issue(issue_id)
        return {"data": None}

    @router.patch(
        "/issues/{issue_id}/flag",
        summary="Set or clear the in-progress flag on a review issue",
    )
    async def flag_review_issue_endpoint(
        issue_id: str,
        request: FlagPipelineIssueRequest,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        issue = await get_issue_by_id(issue_id)
        if issue is None:
            raise HTTPException(status_code=404)
        await set_issue_flagged(issue_id, request.is_flagged)
        return {"data": None}

    @router.get(
        "/issues/{issue_id}/details",
        summary="Per-request source context for a review issue (lazy-load for modal)",
    )
    async def get_review_issue_details_endpoint(
        issue_id: str,
        identity: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        issue = await get_issue_by_id(issue_id)
        if issue is None:
            raise HTTPException(status_code=404)

        raw = await get_issue_request_details(issue["request_ids"])
        issue_type = issue["issue_type"]
        issue_key = issue["issue_key"]

        is_admin = has_at_least(identity.role, Role.ADMINS)

        if issue_type in ("pipeline_error", "no_info", "domain_inactive", "domain_navigation_error"):
            request_id = issue["issue_key"]
            base_rows = [_build_request_row(raw[0], issue_type, issue_key) if raw else {"request_id": request_id}]
            issue_data = issue.get("data") or {}
            error = issue_data.get("error")
            failure_reason = issue_data.get("failure_reason")
            failure_source = issue_data.get("failure_source")
        else:
            base_rows = [_build_request_row(r, issue_type, issue_key) for r in raw]
            error = None
            failure_reason = None
            failure_source = None

        rows = []
        for row in base_rows:
            req_id = row.get("request_id")
            folder = row.get("jurisdiction_path")
            debug_key_base = f"{req_id}/data_source/{folder}" if (req_id and folder) else None
            rows.append({
                **row,
                **({"error": error} if error is not None else {}),
                **({"failure_reason": failure_reason} if failure_reason is not None else {}),
                **({"failure_source": failure_source} if failure_source is not None else {}),
                "pipeline_run_log_url": storage_service.get_presigned_url_cached("civicpatch-debug", f"{debug_key_base}/pipeline_run.log") if (debug_key_base and is_admin) else None,
                "pipeline_run_context_url": storage_service.get_presigned_url_cached("civicpatch-debug", f"{debug_key_base}/pipeline_run_context.json") if debug_key_base else None,
                "debug_url": storage_service.get_bucket_url("civicpatch-debug", req_id) if (is_admin and req_id) else None,
            })
        return {"data": rows}

    @router.get(
        "/unrecognized-roles/grouped",
        summary="List unrecognized roles grouped by role text, each with affected request IDs",
    )
    async def get_unrecognized_roles_grouped_endpoint(
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        rows = await get_unrecognized_roles_grouped()
        return {"data": rows}

    @router.post(
        "/unrecognized-roles/grouped/resolve",
        summary="Bulk-resolve review session entries for a grouped unrecognized role",
    )
    async def resolve_unrecognized_roles_grouped_endpoint(
        body: ResolveUnrecognizedRoleGroupRequest,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        await resolve_unrecognized_role_group(body.request_ids)
        return {"data": None}

    @router.get(
        "/{request_id}/status",
        summary="Get pipeline run status and progress",
        description="Retrieve the progress of a specific pipeline run by its request ID.",
        response_model=GetPipelineRunStatusResponse,
        responses={404: {"model": ErrorResponse, "description": "Pipeline run not found"}},
    )
    async def get_pipeline_run_status_endpoint(
        request_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        response = await get_pipeline_run_status(request_id)
        if not response:
            return JSONResponse(
                content=ErrorResponse(error="Pipeline run not found").model_dump(),
                status_code=404,
            )

        return GetPipelineRunStatusResponse(
            request_id=request_id,
            status=response["status"],
            progress=response["progress"],
        )

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
