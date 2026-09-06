import logging
import math
import os
import time
from dataclasses import asdict
from typing import Optional

import lib.files as file_utils
import lib.buckets as buckets
import lib.storage as storage_service
import lib.temporal.client as temporal_service
import services.jurisdiction_scrape_candidate as candidate_service
import services.pipeline_runs as pipeline_run_service
import shared.utils.id_utils
from database.issues import (
    get_issue_by_id,
    get_issue_counts,
    get_issues_page,
    resolve_issue,
    set_issue_flagged,
)
import database.users
from database.publications import dismiss_request
from database.pipeline_run_spend import get_state_spend, DEFAULT_SPEND_WINDOW_DAYS
from database.pipeline_runs import (
    get_active_pipeline_runs,
    get_pipeline_run,
    get_pipeline_run_status,
    register_run,
    update_pipeline_run_status,
)
from database.review_pool import (
    has_open_changeset,
)
from database.changesets import (
    get_issue_request_details,
)
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole, has_at_least
from schemas.pipeline_runs import (
    BatchPipelineRunRequest,
    CreatePipelineRunRequest,
    CreatePipelineRunResponse,
    ErrorResponse,
    FlagPipelineIssueRequest,
    GetPipelineRunStatusResponse,
    HandleSubmitPipelineRunArtifactsRequest,
    RegisterPipelineRunRequest,
    ServerDetail,
    UpdatePipelineRunStatusRequest,
    UpdatePipelineRunStatusResponse,
)
from services import people_collector
from shared.utils.statuses import (
    RUN_LEVEL_ISSUE_TYPES,
    ChangesetKind,
    DismissalReason,
    PipelineRunStatus,
)

logger = logging.getLogger(__name__)

_is_production = os.getenv("APP_ENVIRONMENT", "").lower() == "production"

# The environment decides, not the caller. A remote dispatch outside production starts a real
# GitHub Actions run that cannot reach this host to register itself, and a local dispatch in
# production has no pipeline to reach — so neither is a choice worth offering.
_DISPATCH_MODE_LOCAL = "local"
DISPATCH_MODE = "remote" if _is_production else _DISPATCH_MODE_LOCAL


ARTIFACTS_BASE_URL = storage_service.get_civicpatch_artifacts_url("").rstrip("/")
PAUSED_CONTEXT_BUCKET = buckets.ARTIFACTS


def _build_request_row(r: dict) -> dict:
    args = r.get("arguments_json") or {}
    url = args.get("url")
    return {
        "changeset_id": r.get("changeset_id"),
        "jurisdiction_ocdid": r.get("jurisdiction_ocdid"),
        "jurisdiction_name": r.get("jurisdiction_name"),
        # The page's URL is its ocdid; the frontend encodes it.
        "jurisdiction_path": r.get("jurisdiction_ocdid"),
        "url": url,
        "source_urls": [url] if url else [],
    }


async def _register_pipeline_run_bg(request: RegisterPipelineRunRequest) -> None:
    try:
        await register_run(
            run_id=request.pipeline_run_id,
            if_not_exists=True,
            arguments_json={
                "jurisdiction_ocdid": request.jurisdiction_ocdid,
                "name": request.name,
                "url": request.url,
                "source_urls": None,
            },
            jurisdiction_ocdid=request.jurisdiction_ocdid,
        )
    except Exception:
        logger.exception(
            f"[{request.pipeline_run_id}] Failed to register pipeline run in background"
        )


# Bounded: an unbounded window is an unbounded scan for anyone editing the query string.
MIN_SPEND_WINDOW_DAYS = 1
MAX_SPEND_WINDOW_DAYS = 365


def get_router(api_key_header):
    router = APIRouter()

    # Declared first: it must not be swallowed by the `/{pipeline_run_id}` paths below.
    # Admin-only, unlike the run counts it sits beside on the Activity page — what the
    # roster says is public, what it cost us to find out is not.
    @router.get(
        "/spend",
        summary="What scraping cost, per state",
        description=(
            "Total spend and average cost per run over the window, by state. States that ran "
            "nothing are absent rather than zero. Excludes grounded Google calls, which state "
            "no cost."
        ),
    )
    async def get_state_spend_endpoint(
        window_days: int = Query(
            DEFAULT_SPEND_WINDOW_DAYS, ge=MIN_SPEND_WINDOW_DAYS, le=MAX_SPEND_WINDOW_DAYS
        ),
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        return {"data": await get_state_spend(window_days)}

    @router.post(
        "",
        summary="Trigger a people collector pipeline run",
        description="Trigger a new people collector pipeline run.",
        response_model=CreatePipelineRunResponse,
        responses={
            409: {
                "model": ErrorResponse,
                "description": "A scrape for this jurisdiction is already running or awaiting review",
            },
            429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
            500: {"model": ErrorResponse, "description": "Internal server error"},
        },
    )
    async def create_people_pipeline_run_endpoint(
        request: CreatePipelineRunRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        if await has_open_changeset(request.jurisdiction_ocdid):
            return JSONResponse(
                content=ErrorResponse(
                    error="A scrape for this jurisdiction is already in flight"
                ).model_dump(),
                status_code=409,
            )

        try:
            pipeline_run_id = shared.utils.id_utils.make_id()
            await register_run(
                run_id=pipeline_run_id,
                arguments_json={
                    "jurisdiction_ocdid": request.jurisdiction_ocdid,
                    "name": request.name,
                    "url": request.url,
                    "source_urls": request.source_urls,
                },
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                created_by_user_id=user.user_id,
            )
            await temporal_service.start_people_collector_workflow(
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                pipeline_run_id=pipeline_run_id,
                dispatch_mode=DISPATCH_MODE,
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

        return CreatePipelineRunResponse(
            pipeline_run_id=pipeline_run_id, status=PipelineRunStatus.PENDING
        )

    @router.post(
        "/batch", summary="Start this state's scrape as one durable workflow"
    )
    async def create_batch_pipeline_runs_endpoint(
        request: BatchPipelineRunRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Starts the workflow and returns; it picks its own candidates.

        This used to select candidates and register a changeset per jurisdiction *before*
        starting Temporal. Two reasons it does not any more:

        - a crash between the writes and the start left orphaned pending changesets that
          nothing would ever complete;
        - a Temporal Schedule can only pass fixed arguments, so a scheduled scrape can hand
          the workflow a state and nothing else. The manual path now ends where a scheduled
          one will.
        """
        workflow_id = await temporal_service.start_state_scrape_workflow(
            request.state, request.num_jurisdictions, user.user_id
        )
        return {"data": {"workflow_id": workflow_id, "state": request.state}}

    @router.post("/batch/claim", include_in_schema=False)
    async def claim_scrape_candidates_endpoint(
        request: BatchPipelineRunRequest,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        """What the workflow calls to find its work. Synchronous, unlike `/register`: the
        workflow must know the changesets exist before it dispatches anything at them."""
        try:
            items = await candidate_service.claim_scrape_candidates(
                request.state, request.num_jurisdictions, request.created_by_user_id
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"data": {"jurisdictions": items}}

    @router.post("/register", include_in_schema=False)
    async def register_pipeline_run_endpoint(
        request: RegisterPipelineRunRequest,
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        background_tasks.add_task(_register_pipeline_run_bg, request)
        return {"data": {"pipeline_run_id": request.pipeline_run_id}}


    @router.get("/{pipeline_run_id}/config", include_in_schema=False)
    async def get_pipeline_run_config_endpoint(
        pipeline_run_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        pipeline_run = await get_pipeline_run(pipeline_run_id)
        if not pipeline_run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        args = pipeline_run.get("arguments_json") or {}
        return {
            "name": args.get("name"),
            "url": args.get("url"),
            "source_urls": args.get("source_urls"),
            # Asked for rather than carried: the run already knows its cap, so nothing
            # between here and the scraper has to pass it along — not the workflow, not the
            # activities, not the Actions workflow in the other repo. Null means inherit.
            "pipeline_run_cap_usd": pipeline_run.get("pipeline_run_cap_usd"),
        }

    # ── Pipeline Runs: Status & Progress ──────────────

    @router.patch(
        "/{pipeline_run_id}/status",
        summary="Update pipeline run status and progress",
        description="Update status and/or progress of a specific pipeline run by its run ID.",
        include_in_schema=False,
    )
    async def patch_pipeline_run_status_endpoint(
        pipeline_run_id: str,
        request: UpdatePipelineRunStatusRequest,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        background_tasks.add_task(
            pipeline_run_service.apply_pipeline_run_status,
            pipeline_run_id,
            request.status,
            request.progress,
            request.jurisdiction_ocdid,
            request.error_type,
            request.error_detail,
        )

        return UpdatePipelineRunStatusResponse(
            pipeline_run_id=pipeline_run_id, status=request.status, progress=request.progress
        )

    # ── Pipeline Runs: Submit & Results ───────────────

    @router.post(
        "/{pipeline_run_id}/submit",
        summary="Upload zip file containing municipal data",
        description="Accepts a zip file containing municipal data and processes it",
        include_in_schema=False,
    )
    async def submit_people_endpoint(
        pipeline_run_id: str,
        file: UploadFile,
        background_tasks: BackgroundTasks,
        jurisdiction_ocdid: str = Form(...),
        pipeline_run_status: Optional[str] = Form(None),
        env: str = Form("production"),
        _user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
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

        logger.info(f"Processing intake for {pipeline_run_id} - {jurisdiction_ocdid}")

        file_path, temp_dir = await file_utils.save_upload_to_temp(file)

        request_obj = HandleSubmitPipelineRunArtifactsRequest(
            pipeline_run_id=pipeline_run_id,
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
            f"[{pipeline_run_id}] Total endpoint time: {time.time() - start_time:.3f}s"
        )
        return {"pipeline_run_id": pipeline_run_id, "status": "processing"}

    @router.post(
        "/{pipeline_run_id}/cancel",
        summary="Cancel a running pipeline run",
        description="Cancel the Temporal workflow for this pipeline run.",
    )
    async def cancel_pipeline_run_endpoint(
        pipeline_run_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        pipeline_run = await get_pipeline_run(pipeline_run_id)
        if not pipeline_run:
            return JSONResponse(
                content=ErrorResponse(error="Pipeline run not found").model_dump(),
                status_code=404,
            )
        jurisdiction_ocdid = (pipeline_run.get("arguments_json") or {}).get(
            "jurisdiction_ocdid"
        )
        if not jurisdiction_ocdid:
            return JSONResponse(
                content=ErrorResponse(
                    error="No jurisdiction_ocdid for pipeline run"
                ).model_dump(),
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
        await update_pipeline_run_status(
            run_id=pipeline_run_id, status=PipelineRunStatus.CANCELLED, progress=None
        )
        # Cancelling settles the proposal too. Stopping a scrape is a person deciding it will
        # not be published, which is what dismissal means. A run cancelled before ingest minted
        # none, so there is nothing to settle.
        minted = pipeline_run.get("changeset_id")
        if minted:
            user_id = await database.users.get_user_id_by_provider(
                user.provider, user.provider_user_id
            )
            await dismiss_request(
                minted, DismissalReason.CANCELLED, resolved_by_user_id=user_id
            )
        return {"pipeline_run_id": pipeline_run_id, "status": PipelineRunStatus.CANCELLED}

    @router.get(
        "/{pipeline_run_id}/temporal-workflow-state",
        summary="What a running scrape's workflow is doing",
        description=(
            "Live Temporal state for a scrape still in flight: the pending activity, its "
            "attempt, and why the last one failed. Returns null data when nothing is running "
            "— a finished run has nothing to say that its status does not say better."
        ),
    )
    async def get_temporal_workflow_state_endpoint(
        pipeline_run_id: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        pipeline_run = await get_pipeline_run(pipeline_run_id)
        if not pipeline_run:
            return JSONResponse(
                content=ErrorResponse(error="Pipeline run not found").model_dump(),
                status_code=404,
            )
        jurisdiction_ocdid = (pipeline_run.get("arguments_json") or {}).get(
            "jurisdiction_ocdid"
        )
        if not jurisdiction_ocdid:
            return {"data": None}
        try:
            state = await temporal_service.describe_workflow(jurisdiction_ocdid)
        except Exception as e:
            # Diagnostics must not take the page down with them: a maintainer looking at a
            # stuck scrape still needs the history that renders beside this.
            logger.warning(f"Could not describe workflow for {pipeline_run_id}: {e}")
            return {"data": None}
        return {"data": asdict(state) if state else None}

    @router.get(
        "/active",
        summary="List currently active (non-terminal) pipeline runs, optionally filtered by state",
    )
    async def get_active_pipeline_runs_endpoint(
        state_code: Optional[str] = None,
        page: int = 1,
        per_page: int = 25,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.CONTRIBUTORS)
        ),
    ):
        pipeline_runs, total = await get_active_pipeline_runs(
            state_code=state_code, page=page, per_page=per_page
        )
        for run in pipeline_runs:
            run["jurisdiction_path"] = run["jurisdiction_ocdid"]
        return {
            "data": pipeline_runs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 1,
        }

    @router.get("/issues/counts", summary="Count pending issues grouped by issue_type")
    async def get_issue_counts_endpoint(
        state_code: Optional[str] = None,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
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
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        issue_types = [t.strip() for t in tags.split(",")] if tags else []
        sort_desc = sort != "asc"
        rows, total = await get_issues_page(
            issue_types,
            page,
            per_page,
            sort_desc,
            state_code=state_code,
            show_archived=show_archived,
        )
        return {"data": rows, "total": total}

    @router.post(
        "/issues/{issue_id}/resolve",
        summary="Mark a review issue as resolved",
    )
    async def resolve_review_issue_endpoint(
        issue_id: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
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
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
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
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
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
        identity: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        issue = await get_issue_by_id(issue_id)
        if issue is None:
            raise HTTPException(status_code=404)

        raw = await get_issue_request_details(issue["changeset_ids"])
        issue_type = issue["issue_type"]
        issue_key = issue["issue_key"]

        is_admin = has_at_least(identity.role, UserRole.ADMINS)

        if issue_type in RUN_LEVEL_ISSUE_TYPES:
            changeset_id = issue["issue_key"]
            base_rows = [
                _build_request_row(raw[0])
                if raw
                else {"changeset_id": changeset_id}
            ]
            issue_data = issue.get("data") or {}
            error = issue_data.get("error")
            failure_reason = issue_data.get("failure_reason")
            failure_source = issue_data.get("failure_source")
        else:
            base_rows = [_build_request_row(r) for r in raw]
            error = None
            failure_reason = None
            failure_source = None

        rows = []
        for row in base_rows:
            req_id = row.get("changeset_id")
            folder = row.get("jurisdiction_path")
            debug_key_base = (
                f"{req_id}/data_source/{folder}" if (req_id and folder) else None
            )
            rows.append(
                {
                    **row,
                    **({"error": error} if error is not None else {}),
                    **(
                        {"failure_reason": failure_reason}
                        if failure_reason is not None
                        else {}
                    ),
                    **(
                        {"failure_source": failure_source}
                        if failure_source is not None
                        else {}
                    ),
                    "pipeline_run_log_url": storage_service.get_presigned_url_cached(
                        buckets.DEBUG, f"{debug_key_base}/pipeline_run.log"
                    )
                    if (debug_key_base and is_admin)
                    else None,
                    "pipeline_run_context_url": storage_service.get_presigned_url_cached(
                        buckets.DEBUG,
                        f"{debug_key_base}/pipeline_run_context.json",
                    )
                    if debug_key_base
                    else None,
                    "debug_url": storage_service.get_bucket_url(
                        buckets.DEBUG, req_id
                    )
                    if (is_admin and req_id)
                    else None,
                }
            )
        return {"data": rows}

    @router.get(
        "/{pipeline_run_id}/status",
        summary="Get pipeline run status and progress",
        description="Retrieve the progress of a specific pipeline run by its run ID.",
        response_model=GetPipelineRunStatusResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Pipeline run not found"}
        },
    )
    async def get_pipeline_run_status_endpoint(
        pipeline_run_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        response = await get_pipeline_run_status(pipeline_run_id)
        if not response:
            return JSONResponse(
                content=ErrorResponse(error="Pipeline run not found").model_dump(),
                status_code=404,
            )

        return GetPipelineRunStatusResponse(
            pipeline_run_id=pipeline_run_id,
            status=response["status"],
            progress=response["progress"],
        )

    @router.get(
        "/{pipeline_run_id}/context/upload-url",
        summary="Get a presigned PUT URL for uploading paused workflow context",
        include_in_schema=False,
    )
    async def get_context_upload_url_endpoint(
        pipeline_run_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{pipeline_run_id}/paused_context.json"
        url = storage_service.get_presigned_put_url(PAUSED_CONTEXT_BUCKET, key)
        return {"url": url}

    @router.get(
        "/{pipeline_run_id}/context/download-url",
        summary="Get a presigned GET URL for downloading paused workflow context",
        include_in_schema=False,
    )
    async def get_context_download_url_endpoint(
        pipeline_run_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{pipeline_run_id}/paused_context.json"
        url = storage_service.get_presigned_url_cached(PAUSED_CONTEXT_BUCKET, key)
        return {"url": url}

    @router.delete(
        "/{pipeline_run_id}/context",
        summary="Delete paused workflow context from storage",
        include_in_schema=False,
    )
    async def delete_context_endpoint(
        pipeline_run_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{pipeline_run_id}/paused_context.json"
        storage_service.delete_object(PAUSED_CONTEXT_BUCKET, key)
        return {"pipeline_run_id": pipeline_run_id}

    return router
