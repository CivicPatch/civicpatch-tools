import asyncio
import json
import logging
import math
import os
import time
from typing import Optional
import shared.utils.data_path_utils as data_path_utils
import shared.utils.id_utils
from shared.utils.statuses import PipelineRunStatus, PullRequestStatus
import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

import lib.github.api as github_service
from lib.github.pr import PrAuthor
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
from database.pipeline_issues import (
    get_pipeline_issues_page,
    get_pipeline_issue_by_id,
    get_unrecognized_roles_grouped,
    resolve_unrecognized_role_group,
    resolve_pipeline_issue,
    open_pipeline_issue_pull_request,
    upsert_pipeline_issue,
)
from database.pull_requests import (
    update_pipeline_run_pull_request_url,
    update_pipeline_run_pull_request_status,
)
from database.requests import (
    register_request_with_pipeline_run,
    get_request_jurisdiction,
    get_issue_request_details,
)
from core import people_collector
import core.review_issue_resolution as review_issue_resolution_service
from schemas.common import Identity, Jurisdiction, Role, RouteCategory
from schemas.pipeline_runs import (
    CreatePipelineRunRequest,
    BatchPipelineRunRequest,
    RegisterGithubRunRequest,
    UpdatePipelineRunStatusRequest,
    UpdatePipelineRunStatusResponse,
    PostPipelineRunResultRequest,
    ResolveUnrecognizedRoleGroupRequest,
    CreatePipelineRunResponse,
    GetPipelineRunResponse,
    GetPipelineRunStatusResponse,
    ErrorResponse,
)
from schemas.requests import HandleSubmitPipelineRunArtifactsRequest, ResolveIssueRequest, ServerDetail
import lib.pubsub as pubsub_service
from lib.auth import require_route_access

logger = logging.getLogger(__name__)

_is_production = os.getenv("APP_ENVIRONMENT", "").lower() == "production"


ARTIFACTS_BASE_URL = "https://civicpatch-artifacts.civicpatch.org"
PAUSED_CONTEXT_BUCKET = "civicpatch-artifacts"


async def update_pipeline_run_and_publish(request_id: str, status: str, progress: Optional[int], jurisdiction_ocdid: Optional[str]):
    await update_pipeline_run_status(request_id=request_id, status=status, progress=progress)
    if status == PipelineRunStatus.ERROR:
        await upsert_pipeline_issue(request_id, "pipeline_error", [{"error": "workflow failure"}])
    if not jurisdiction_ocdid:
        pipeline_run = await get_pipeline_run(request_id)
        jurisdiction_ocdid = (pipeline_run.get("arguments_json") or {}).get("jurisdiction_ocdid") if pipeline_run else None
    if jurisdiction_ocdid:
        await pubsub_service.publish(
            f"job_status:{jurisdiction_ocdid}",
            json.dumps({"request_id": request_id, "status": status, "progress": progress}),
        )


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
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])
        ),
    ):
        background_tasks.add_task(
            update_pipeline_run_and_publish,
            request_id,
            request.status,
            request.progress,
            request.jurisdiction_ocdid,
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

        file_path, temp_dir = await file_utils.save_upload_to_temp(file)

        request_obj = HandleSubmitPipelineRunArtifactsRequest(
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            server_detail=ServerDetail(
                user_email="jobs-people@civicpatch.org", server_url="civicpatch.org"
            ),
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
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, ["admins"])),
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
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.CONTRIBUTORS])),
    ):
        pipeline_runs, total = await get_active_pipeline_runs(state_code=state_code, page=page, per_page=per_page)
        for run in pipeline_runs:
            run["jurisdiction_path"] = shared.utils.id_utils.jurisdiction_ocdid_to_folder(run["jurisdiction_ocdid"])
        return {"data": pipeline_runs, "total": total, "page": page, "per_page": per_page, "total_pages": math.ceil(total / per_page) if total else 1}

    @router.get(
        "/issues",
        summary="List review issues (unrecognized roles, dead URLs, etc.) with pagination",
    )
    async def get_review_issues_endpoint(
        tags: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
        sort: str = "desc",
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])),
    ):
        issue_types = [t.strip() for t in tags.split(",")] if tags else []
        sort_desc = sort != "asc"
        rows, total = await get_pipeline_issues_page(issue_types, page, per_page, sort_desc)
        return {"data": rows, "total": total}

    @router.post(
        "/issues/{issue_id}/resolve",
        summary="Mark a review issue as resolved",
    )
    async def resolve_review_issue_endpoint(
        issue_id: str,
        body: ResolveIssueRequest = ResolveIssueRequest(),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])),
    ):
        issue = await get_pipeline_issue_by_id(issue_id)
        if issue is None:
            raise HTTPException(status_code=404)

        author = PrAuthor(
            name=user.display_name or user.email or user.provider_user_id,
            email=user.email or f"{user.provider_user_id}@users.noreply.github.com",
        )

        config_path = None
        pull_request_url = None
        if issue["issue_type"] == "unrecognized_role":
            result = await review_issue_resolution_service.resolve_role_issue(issue, body, author)
            pull_request_url, config_path = result if result else (None, None)
        else:
            await resolve_pipeline_issue(issue_id)
            return {"data": None}

        if pull_request_url:
            await open_pipeline_issue_pull_request(issue_id, pull_request_url)
            data: dict = {"pull_request_url": pull_request_url}
            if config_path:
                data["config_path"] = config_path
            return {"data": data}

        await resolve_pipeline_issue(issue_id)
        return {"data": None}

    @router.post(
        "/issues/{issue_id}/dismiss",
        summary="Dismiss a review issue without opening a PR",
    )
    async def dismiss_review_issue_endpoint(
        issue_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])),
    ):
        issue = await get_pipeline_issue_by_id(issue_id)
        if issue is None:
            raise HTTPException(status_code=404)
        await resolve_pipeline_issue(issue_id)
        return {"data": None}

    @router.get(
        "/issues/{issue_id}/details",
        summary="Per-request source context for a review issue (lazy-load for modal)",
    )
    async def get_review_issue_details_endpoint(
        issue_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.MAINTAINERS, Role.ADMINS])),
    ):
        issue = await get_pipeline_issue_by_id(issue_id)
        if issue is None:
            raise HTTPException(status_code=404)

        raw = await get_issue_request_details(issue["request_ids"])
        issue_type = issue["issue_type"]
        issue_key = issue["issue_key"]

        if issue_type in ("pipeline_error", "no_info"):
            request_id = issue["issue_key"]
            jurisdiction_ocdid = raw[0]["jurisdiction_ocdid"] if raw else None
            folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid) if jurisdiction_ocdid else None
            base = f"{ARTIFACTS_BASE_URL}/{request_id}/data_source/{folder}" if folder else None
            return {"data": [{
                "request_id": request_id,
                "error": (issue.get("data") or {}).get("error"),
                "workflow_log_url": f"{base}/pipeline_run.log" if base else None,
                "workflow_context_url": f"{base}/pipeline_run_context.json" if base else None,
                "debug_url": f"https://dash.cloudflare.com/c9ae2b352766fe3e6f7dbee61bcd4c7c/r2/default/buckets/civicpatch-artifacts?prefix={request_id}%2F",
            }]}

        result = []
        for r in raw:
            args = r["arguments_json"]
            people = []
            source_urls = []
            if issue_type == "unrecognized_role":
                matching = [
                    p for p in (r["data_json"] or [])
                    if isinstance(p, dict) and (p.get("office") or {}).get("name", "") == issue_key
                ]
                people = [{"name": p["name"]} for p in matching]
                source_urls = list({u for p in matching for u in (p.get("source_urls") or [])})
            else:
                source_urls = [args["url"]] if args.get("url") else []
            folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(r["jurisdiction_ocdid"]) if r["jurisdiction_ocdid"] else None
            result.append({
                "request_id": r["request_id"],
                "jurisdiction_ocdid": r["jurisdiction_ocdid"],
                "jurisdiction_name": r["jurisdiction_name"],
                "jurisdiction_path": folder,
                "url": args.get("url"),
                "source_urls": source_urls,
                "people": people,
            })
        return {"data": result}

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

    # -- Pipeline Runs: List pipeline runs where the pull requests have duplicate jurisdictions ──
    @router.get(
        "/duplicates",
        summary="List pipeline runs where the pull requests have duplicate jurisdictions",
    )
    async def list_pipeline_runs_with_duplicate_jurisdictions_endpoint(
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        jurisdiction_ocdids = await database.pipeline_runs.get_duplicate_jurisdiction_ocdids()
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
        stale = await database.pipeline_runs.get_stale_duplicate_pr_info()
        closed, failed = [], []
        for item in stale:
            success = await github_service.close_pull_request(str(item["pr_number"]))
            if success:
                await update_pipeline_run_pull_request_status(item["request_id"], PullRequestStatus.CLOSED)
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
