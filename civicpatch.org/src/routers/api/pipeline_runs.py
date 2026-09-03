import json
import logging
import math
import os
import time
from dataclasses import asdict
from typing import Optional

import lib.files as file_utils
import lib.pubsub as pubsub_service
import lib.buckets as buckets
import lib.storage as storage_service
import lib.temporal.client as temporal_service
import services.jurisdiction_scrape_candidate as candidate_service
import shared.utils.id_utils
from database.issues import (
    get_issue_by_id,
    get_issue_counts,
    get_issues_page,
    resolve_issue,
    set_issue_flagged,
    supersede_prior_jurisdiction_issues,
)
import database.users
from database.publications import dismiss_request
from database.pipeline_runs import (
    get_active_pipeline_runs,
    get_pipeline_run,
    get_pipeline_run_status,
    update_pipeline_run_status,
)
from database.review_pool import (
    has_open_changeset,
)
from database.changesets import (
    get_issue_request_details,
    register_request_with_pipeline_run,
    register_request_with_pipeline_run_if_not_exists,
)
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
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
    ChangesetKind,
    DismissalReason,
    TERMINAL_PIPELINE_RUN_STATUSES,
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


# Terminal statuses that produce nothing to review. Their requests are dismissed so they stop
# counting as pending work.
ENDED_WITHOUT_A_ROSTER = frozenset(
    {PipelineRunStatus.CANCELLED, PipelineRunStatus.ERROR}
)


async def finalize_pipeline_run(
    changeset_id: str, status: str, jurisdiction_ocdid: Optional[str]
) -> None:
    """A run reached a state it will not leave. Settle what was waiting on it.

    Only terminal statuses get here — a run at 40% has nothing to settle.

    A run that ended without a roster has to leave the review queue. Otherwise its request
    derives as `pending` forever, and pending requests are what populate the jurisdiction
    page's list *and* disable roster editing — so every failure left a permanent blocker
    behind. Measured before widening this: 8 pending ERROR runs, none carrying a roster.

    `SUCCESS` and `RESOLVED` are excluded because they produce something to review. Named
    rather than written as "not SUCCESS", so a status added later has to be considered instead
    of silently inheriting dismissal.

    No user id: a machine giving up is exactly what `resolved_by_user_id IS NULL` distinguishes
    from a person declining. A retry is a new run and a new request; this one is over either
    way.
    """
    if status in ENDED_WITHOUT_A_ROSTER:
        await dismiss_request(changeset_id, DismissalReason.ERRORED)

    if jurisdiction_ocdid:
        await supersede_prior_jurisdiction_issues(jurisdiction_ocdid, changeset_id)


async def apply_pipeline_run_status(
    changeset_id: str,
    status: str,
    progress: Optional[int],
    jurisdiction_ocdid: Optional[str],
    error_type: Optional[str] = None,
    error_detail: Optional[dict] = None,
):
    """A run reported a status — store it, settle it if it is over, tell the page.

    Named for the input because the consequences differ by status: every report is stored and
    pushed to the `pipeline_run_status` topic the jurisdiction page listens on, but only a
    terminal one finalizes anything.

    Not "publish", which everywhere else here means a roster going live — the opposite of what
    a cancelled run does.
    """
    await update_pipeline_run_status(
        changeset_id=changeset_id, status=status, progress=progress
    )

    # The reporter does not always know it; the run's own arguments do.
    if not jurisdiction_ocdid:
        pipeline_run = await get_pipeline_run(changeset_id)
        jurisdiction_ocdid = (
            (pipeline_run.get("arguments_json") or {}).get("jurisdiction_ocdid")
            if pipeline_run
            else None
        )

    if status in TERMINAL_PIPELINE_RUN_STATUSES:
        await finalize_pipeline_run(changeset_id, status, jurisdiction_ocdid)

    if jurisdiction_ocdid:
        await pubsub_service.publish(
            f"pipeline_run_status:{jurisdiction_ocdid}",
            json.dumps(
                {
                    "changeset_id": changeset_id,
                    "status": status,
                    "progress": progress,
                    # Same answer the history rows carry, so a live update and a fetched row
                    # cannot disagree about whether the scrape is still going.
                    "is_running": status not in TERMINAL_PIPELINE_RUN_STATUSES,
                }
            ),
        )


async def _register_pipeline_run_bg(request: RegisterPipelineRunRequest) -> None:
    try:
        await register_request_with_pipeline_run_if_not_exists(
            changeset_id=request.changeset_id,
            kind=ChangesetKind.SCRAPE,
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
            f"[{request.changeset_id}] Failed to register pipeline run in background"
        )


def get_router(api_key_header):
    router = APIRouter()

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
            changeset_id = shared.utils.id_utils.make_changeset_id()
            await register_request_with_pipeline_run(
                changeset_id=changeset_id,
                kind=ChangesetKind.SCRAPE,
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
                changeset_id=changeset_id,
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
            changeset_id=changeset_id, status=PipelineRunStatus.PENDING
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
        return {"data": {"changeset_id": request.changeset_id}}


    @router.get("/{changeset_id}/config", include_in_schema=False)
    async def get_pipeline_run_config_endpoint(
        changeset_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        pipeline_run = await get_pipeline_run(changeset_id)
        if not pipeline_run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        args = pipeline_run.get("arguments_json") or {}
        return {
            "name": args.get("name"),
            "url": args.get("url"),
            "source_urls": args.get("source_urls"),
        }

    # ── Pipeline Runs: Status & Progress ──────────────

    @router.patch(
        "/{changeset_id}/status",
        summary="Update pipeline run status and progress",
        description="Update status and/or progress of a specific pipeline run by its request ID.",
        include_in_schema=False,
    )
    async def patch_pipeline_run_status_endpoint(
        changeset_id: str,
        request: UpdatePipelineRunStatusRequest,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        background_tasks.add_task(
            apply_pipeline_run_status,
            changeset_id,
            request.status,
            request.progress,
            request.jurisdiction_ocdid,
            request.error_type,
            request.error_detail,
        )

        return UpdatePipelineRunStatusResponse(
            changeset_id=changeset_id, status=request.status, progress=request.progress
        )

    # ── Pipeline Runs: Submit & Results ───────────────

    @router.post(
        "/{changeset_id}/submit",
        summary="Upload zip file containing municipal data",
        description="Accepts a zip file containing municipal data and processes it",
        include_in_schema=False,
    )
    async def submit_people_endpoint(
        changeset_id: str,
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

        logger.info(f"Processing intake for {changeset_id} - {jurisdiction_ocdid}")

        file_path, temp_dir = await file_utils.save_upload_to_temp(file)

        request_obj = HandleSubmitPipelineRunArtifactsRequest(
            changeset_id=changeset_id,
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
            f"[{changeset_id}] Total endpoint time: {time.time() - start_time:.3f}s"
        )
        return {"changeset_id": changeset_id, "status": "processing"}

    @router.post(
        "/{changeset_id}/cancel",
        summary="Cancel a running pipeline run",
        description="Cancel the Temporal workflow for this pipeline run.",
    )
    async def cancel_pipeline_run_endpoint(
        changeset_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        pipeline_run = await get_pipeline_run(changeset_id)
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
            changeset_id=changeset_id, status=PipelineRunStatus.CANCELLED, progress=None
        )
        # Cancelling settles the review too. Stopping a scrape is a person deciding it will not
        # be published, which is what dismissal means — and without this the request sits at
        # "pending" forever, since nothing will ever review a run that did not finish.
        user_id = await database.users.get_user_id_by_provider(user.provider, user.provider_user_id)
        await dismiss_request(
            changeset_id, DismissalReason.CANCELLED, resolved_by_user_id=user_id
        )
        return {"changeset_id": changeset_id, "status": PipelineRunStatus.CANCELLED}

    @router.get(
        "/{changeset_id}/temporal-workflow-state",
        summary="What a running scrape's workflow is doing",
        description=(
            "Live Temporal state for a scrape still in flight: the pending activity, its "
            "attempt, and why the last one failed. Returns null data when nothing is running "
            "— a finished run has nothing to say that its status does not say better."
        ),
    )
    async def get_temporal_workflow_state_endpoint(
        changeset_id: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
        ),
    ):
        pipeline_run = await get_pipeline_run(changeset_id)
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
            logger.warning(f"Could not describe workflow for {changeset_id}: {e}")
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

        if issue_type in (
            "pipeline_error",
            "no_info",
            "domain_inactive",
            "domain_navigation_error",
        ):
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
        "/{changeset_id}/status",
        summary="Get pipeline run status and progress",
        description="Retrieve the progress of a specific pipeline run by its request ID.",
        response_model=GetPipelineRunStatusResponse,
        responses={
            404: {"model": ErrorResponse, "description": "Pipeline run not found"}
        },
    )
    async def get_pipeline_run_status_endpoint(
        changeset_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        response = await get_pipeline_run_status(changeset_id)
        if not response:
            return JSONResponse(
                content=ErrorResponse(error="Pipeline run not found").model_dump(),
                status_code=404,
            )

        return GetPipelineRunStatusResponse(
            changeset_id=changeset_id,
            status=response["status"],
            progress=response["progress"],
        )

    @router.get(
        "/{changeset_id}/context/upload-url",
        summary="Get a presigned PUT URL for uploading paused workflow context",
        include_in_schema=False,
    )
    async def get_context_upload_url_endpoint(
        changeset_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{changeset_id}/paused_context.json"
        url = storage_service.get_presigned_put_url(PAUSED_CONTEXT_BUCKET, key)
        return {"url": url}

    @router.get(
        "/{changeset_id}/context/download-url",
        summary="Get a presigned GET URL for downloading paused workflow context",
        include_in_schema=False,
    )
    async def get_context_download_url_endpoint(
        changeset_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{changeset_id}/paused_context.json"
        url = storage_service.get_presigned_url_cached(PAUSED_CONTEXT_BUCKET, key)
        return {"url": url}

    @router.delete(
        "/{changeset_id}/context",
        summary="Delete paused workflow context from storage",
        include_in_schema=False,
    )
    async def delete_context_endpoint(
        changeset_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.SERVICE)),
    ):
        key = f"{changeset_id}/paused_context.json"
        storage_service.delete_object(PAUSED_CONTEXT_BUCKET, key)
        return {"changeset_id": changeset_id}

    return router
