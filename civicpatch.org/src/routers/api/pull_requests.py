import asyncio
import json
import logging
import os
from typing import List, Optional
from shared.schemas import Official
import shared.utils.data_path_utils
import shared.utils.id_utils
import shared.utils.url_utils
from shared.utils.statuses import PullRequestStatus
import yaml
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import database.issues
import database.pipeline_runs
import database.requests as requests_db
import database.people
import database.jurisdictions as jurisdictions_db
import database.pull_requests as pull_requests_db
import database.review_sessions as review_sessions_db
import database.review_session_entries as review_session_entries_db
import database.users
import lib.github.api as github_service
import services.change_logs as change_logs
import services.review_issue_report as review_issue_report_service
from core.people_patch import PersonPatch, patch_people, PeopleValidationError
from core.review_mode import review_mode_for
import services.pull_request_sync as pr_sync_service
from services.review_proposal import (
    proposals_for_requests,
    review_summary_for_request,
)
from services.publish import (
    dismiss_people,
    promote_images,
    promote_to_reviewed,
    publish_people,
)
import lib.redis as redis_store
import lib.buckets as buckets
import lib.storage as storage_service
from database.people import DEFAULT_VIEW, VIEWS
from schemas.common import Identity, ReportReviewIssueRequest, UserRole, RouteCategory
from lib.auth import require_route_access

logger = logging.getLogger(__name__)


def _source_url_to_markdown_url(request_id: str, jurisdiction_ocdid_folder: str, source_url: str) -> Optional[str]:
    source_url_dir = shared.utils.url_utils.format_url_to_folder(source_url)
    relative_path = os.path.join(request_id, "data_source", jurisdiction_ocdid_folder, "cache", source_url_dir, "preprocessed.md")
    return storage_service.get_presigned_url_cached(buckets.DEBUG, relative_path)


def build_sources(request_id: str, jurisdiction_ocdid: str, source_urls: list[str]) -> list[dict]:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return [{"url": url, "markdown": _source_url_to_markdown_url(request_id, folder, url)} for url in source_urls]

# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────


class SaveAndMergeRequest(BaseModel):
    request_id: str
    jurisdiction_ocdid: str
    data: List[PersonPatch] | None = None


class SaveReviewRequest(BaseModel):
    request_id: str
    jurisdiction_ocdid: str
    data: List[PersonPatch]


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class DeleteJobResponse(BaseModel):
    request_id: str
    status: str


class ErrorResponse(BaseModel):
    error: str


# A scrape whose roster was never recorded cannot be edited or published: `data_json` is the
# only copy now that the job branch is gone. Rescue such rows via `POST /api/admin/pr_sync`.
MISSING_ROSTER_DETAIL = "This scrape has no recorded roster. Re-sync it before reviewing."


async def _commit_people_patch(
    request_id: str,
    jurisdiction_ocdid: str,
    data: List[PersonPatch],
    user: Identity,
) -> List[dict]:
    """Apply the reviewer's edits to the scrape's stored roster."""
    # `data_json` is the base now that edits no longer go to a PR branch. It carries prior
    # edits for the same reason the branch used to: every save writes back to it.
    base = await database.pipeline_runs.get_pipeline_run_data_json(request_id)
    # Patches are sparse, so patching against a missing base does not fail — it writes each
    # person reduced to the fields the reviewer happened to touch. Refuse instead.
    if not base:
        raise HTTPException(status_code=409, detail=MISSING_ROSTER_DETAIL)
    try:
        patched = patch_people(base, data)
    except PeopleValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.failures)

    # Awaited, not backgrounded: this was a background task while the branch write was the
    # authoritative one. It is the only store now, so a 200 must mean the edit is persisted.
    await database.pipeline_runs.update_pipeline_run_data(request_id, patched)
    if user.user_id:
        await change_logs.record_manual_edits(
            request_id, jurisdiction_ocdid, user.user_id, base, patched
        )
    return patched


async def _publish_roster(
    request_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str | None,
) -> None:
    """Make this scrape's roster live. `edited` is the reviewer's patched result; when they
    published without editing, the submitted roster stands."""
    roster = edited
    if roster is None:
        roster = await database.pipeline_runs.get_pipeline_run_data_json(request_id)
    # Publishing an empty roster retires every person in the jurisdiction. That was unreachable
    # while the review pool required an open PR; the request is the only record now.
    if not roster:
        raise HTTPException(status_code=409, detail=MISSING_ROSTER_DETAIL)
    # Photos promote with the data: publishing is what moves them off the artifacts bucket.
    await publish_people(
        request_id, jurisdiction_ocdid, promote_images(roster), resolved_by_user_id
    )
    # The scrape leaves the unreviewed path for the canonical one. Queued, so a slow or failed
    # GitHub write cannot affect a publish that has already committed.
    await promote_to_reviewed(request_id, jurisdiction_ocdid)


# ──────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────


def get_router(api_key_header):
    router = APIRouter()

    # -- Pull Requests: List Open Pull Requests ───────────
    # Note: Used by jurisdiction detail page
    # So that's why this isn't paged. Expect max of 1 pull request
    @router.get(
        "",
        summary="List open pull requests",
    )
    async def list_pull_requests_endpoint(
        jurisdiction_ocdid: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        pull_requests, _, _ = await pull_requests_db.list_open_pull_requests(
            jurisdiction_ocdid=jurisdiction_ocdid
        )
        return {"data": pull_requests}

    # ── Pull Requests: List & Data ───────────
    @router.get(
        "/data",
        summary="Get YAML data from a pull request branch",
    )
    async def get_pull_request_data_endpoint(
        jurisdiction_ocdid: str,
        request_id: str,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        file_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(
            jurisdiction_ocdid
        )

        existing, cached = await asyncio.gather(
            database.people.get_people_by_jurisdiction_ocdid(jurisdiction_ocdid),
            database.pipeline_runs.get_pipeline_run_data_json(request_id),
        )

        # Fast path: serve from DB if already backfilled
        if cached is not None:
            return {
                "request_id": request_id,
                "file_path": file_path,
                "data": cached,
                "existing": existing,
            }

        file_content = await github_service.get_pull_request_file_yaml(
            jurisdiction_ocdid=jurisdiction_ocdid,
            request_id=request_id,
            file_path=f"data/{file_path}.yml",
        )
        if file_content is None:
            # Branch or file not found — trigger a full PR sync in the background
            # so the next request succeeds once the sync completes.
            background_tasks.add_task(pr_sync_service.sync_open_pr_state)
            return JSONResponse(
                content={"error": "Data file not found on branch"}, status_code=404
            )

        # Backfill DB so future requests skip the GitHub roundtrip
        background_tasks.add_task(
            database.pipeline_runs.update_pipeline_run_data, request_id, file_content
        )

        return {
            "request_id": request_id,
            "file_path": file_path,
            "data": file_content,
            "existing": existing,
        }

    # ── Pull Requests: Batch Data ────────────
    @router.get(
        "/with-data",
        summary="Batch get pull request details and data",
    )
    async def get_pull_requests_with_data(
        page: int = 1,
        per_page: int = 10,
        state_code: str | None = None,
        jurisdiction_ocdid: str | None = None,
        view: str = Query(default=DEFAULT_VIEW, pattern=f"^({'|'.join(VIEWS)})$"),
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        paged_pull_requests, total, with_issues = await pull_requests_db.list_open_pull_requests(
            state_code=state_code, jurisdiction_ocdid=jurisdiction_ocdid, page=page, per_page=per_page
        )
        total_pages = (total + per_page - 1) // per_page

        jurisdiction_ocdids = list(
            {pr["jurisdiction"]["ocdid"] for pr in paged_pull_requests if pr.get("jurisdiction")}
        )
        request_ids = list({pr["request_id"] for pr in paged_pull_requests})
        data = await database.people.get_people_data_by_request_ids(
            jurisdiction_ocdids, request_ids, view=view
        )
        # What each scrape would actually change. `existing` and `proposed` are two rosters a
        # reader has to diff by eye; this is the diff.
        proposals = await proposals_for_requests(request_ids)

        results = []
        for pr in paged_pull_requests:
            entry = data.get(pr["request_id"], {})
            proposed = entry.get("proposed", [])
            unique_source_urls = list({url for person in proposed for url in (person.get("source_urls") or [])})
            results.append({
                **pr,
                "existing": entry.get("existing", []),
                "proposed": proposed,
                "changes": [
                    change.model_dump()
                    for change in proposals.get(pr["request_id"], [])
                ],
                "sources": build_sources(pr["request_id"], pr["jurisdiction"]["ocdid"], unique_source_urls),
            })
        return {
            "data": results,
            "total": total,
            "total_pages": total_pages,
            "page": page,
            "per_page": per_page,
            "summary": {
                "total_with_pr": total,
                "with_issues": with_issues,
            },
        }

    # -- Pull Requests: Get by PR number ---
    @router.get("/by-request/{request_id}")
    async def get_pull_request_by_request_id_endpoint(
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        result = await pull_requests_db.get_pull_request_data_by_request_id(request_id)
        if not result:
            raise HTTPException(status_code=404, detail="Pull request not found")

        request_id = result["request_id"]
        jurisdiction_ocdid = result["jurisdiction_ocdid"]
        proposed = result["proposed"] or []

        existing, scraped_at, proposals = await asyncio.gather(
            database.people.get_people_by_jurisdiction_ocdid(jurisdiction_ocdid),
            jurisdictions_db.get_scraped_at(jurisdiction_ocdid),
            # What this scrape would change about who holds what. The queue listing has carried
            # it since the proposal landed; the review session reads this endpoint instead, and
            # without it a proposed person has no post to name — the post does not exist yet, so
            # the derivation is the only thing that knows.
            proposals_for_requests([request_id]),
        )
        unique_source_urls = list({url for person in proposed for url in (person.get("source_urls") or [])})

        return {
            "data": {
                "request_id": request_id,
                "entry_number": 1,
                "has_next": False,
                "has_prev": False,
                "jurisdiction": {
                    "ocdid": jurisdiction_ocdid,
                    "name": result["jurisdiction_name"],
                    "path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid),
                    "website_url": result["jurisdiction_website_url"],
                },
                "pr": result["pr"],
                "mode": review_mode_for(scraped_at).value,
                "existing": existing,
                "proposed": proposed,
                "changes": [
                    change.model_dump()
                    for change in proposals.get(request_id, [])
                ],
                "sources": build_sources(request_id, jurisdiction_ocdid, unique_source_urls),
            }
        }

    # -- Pull Requests: Issues for a job ---
    @router.get("/{request_id}/review")
    async def get_pull_request_review_endpoint(
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        return {"data": await review_summary_for_request(request_id)}

    # -- Pull Requests: Reviewer-filed issues for this request ---
    @router.get("/{request_id}/issues")
    async def get_reported_issues_endpoint(
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        result = await database.issues.get_user_reported_issues_for_request(request_id)
        return {"data": result}

    # -- Pull Requests: Report an issue on open-data ---
    @router.post("/{request_id}/issues")
    async def report_review_issue_endpoint(
        request_id: str,
        body: ReportReviewIssueRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")
        reported_by = user.display_name or user.email or user.provider_user_id
        try:
            result = await review_issue_report_service.report_review_issue(
                request_id, body.description, user.user_id, reported_by
            )
        except review_issue_report_service.ReviewNotFoundError:
            raise HTTPException(status_code=404, detail="Pull request not found")
        except review_issue_report_service.GithubIssueCreationError as e:
            raise HTTPException(status_code=502, detail=str(e))
        return {"data": result}

    # -- Reviews: Dismiss ---
    # Keyed on request_id, not a pull request number: a scrape published straight to open-data
    # has no pull request, and those are the majority now.
    @router.delete("/{request_id}", include_in_schema=False)
    async def close_pull_request_endpoint(
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.CONTRIBUTORS)
        ),
    ):
        user_id = await database.users.get_user_id_by_provider(user.provider, user.provider_user_id)
        # Dismissal is a database write now. Nothing is closed on GitHub because nothing was
        # opened there — `dismissed_at` is what takes the request out of the review pool.
        await dismiss_people(request_id, user_id)
        # Credit the review: closing is a completed review action, same as publishing.
        await review_session_entries_db.resolve_entries_for_request(request_id)
        return {"status": "success"}

    # -- Reviews: Save without publishing ---
    @router.post("/{request_id}/save", include_in_schema=False)
    async def save_review_endpoint(
        request_id: str,
        request: SaveReviewRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        await _commit_people_patch(
            request.request_id, request.jurisdiction_ocdid, request.data, user
        )
        # No merge, no parking: the request stays in AVAILABLE_FOR_REVIEW. The entry is
        # held by its session (see _allocate_next_review) and returns to the pool
        # when that session is released.
        await review_session_entries_db.save_entries_for_request(request.request_id)
        return {"status": "saved"}

    # -- Reviews: Publish ---
    @router.post("/{request_id}/publish", include_in_schema=False)
    async def save_and_merge_endpoint(
        request_id: str,
        request: SaveAndMergeRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        edited = None
        if request.data:
            edited = await _commit_people_patch(
                request.request_id, request.jurisdiction_ocdid, request.data, user
            )

        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")

        # Publishing is a database write, so it is synchronous: a 200 means the roster is live
        # and `published_at` is stamped. The open-data commit is queued behind it and retries
        # on its own — git is the projection, not the record.
        await _publish_roster(
            request.request_id, request.jurisdiction_ocdid, edited, user.user_id
        )
        await review_session_entries_db.resolve_entries_for_request(request.request_id)
        return {"status": "published"}

    # -- Pull Requests: Merge Status ---
    @router.get("/{pull_request_number}/merge-status", include_in_schema=False)
    async def merge_status_endpoint(
        pull_request_number: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.AUTHENTICATED)
        ),
    ):
        raw = await redis_store.get(f"merge_status:{pull_request_number}")
        if not raw:
            return {"status": "pending"}
        return json.loads(raw)

    # -- Pull Requests: Merge Pull Request ---
    @router.post("/{pull_request_number}/merge", include_in_schema=False)
    async def merge_pull_request_endpoint(
        pull_request_number: str,
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.CONTRIBUTORS)
        ),
    ):
        merge_error = await github_service.merge_pull_request(
            pull_request_number=pull_request_number,
            approved_by=user.email,
        )
        if merge_error:
            status_code = 409 if "out of date" in merge_error.lower() else 500
            return JSONResponse(
                content=ErrorResponse(error=merge_error).model_dump(),
                status_code=status_code,
            )
        # No reviewer edits on this path, so the submitted roster is what goes live.
        jurisdiction_ocdid = await requests_db.get_request_jurisdiction(request_id)
        user_id = await database.users.get_user_id_by_provider(user.provider, user.provider_user_id)
        if jurisdiction_ocdid:
            await _publish_roster(request_id, jurisdiction_ocdid, None, user_id)
        await pr_sync_service.apply_pull_request_status(request_id, PullRequestStatus.MERGED, resolved_by_user_id=user_id)
        return {"status": "success"}

    # -- Pull Requests: Update Branch ---
    @router.post("/{pull_request_number}/update-branch", include_in_schema=False)
    async def update_pull_request_branch_endpoint(
        pull_request_number: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.CONTRIBUTORS)
        ),
    ):
        error = await github_service.update_pull_request_branch(
            pull_request_number=pull_request_number,
        )
        if error:
            return JSONResponse(
                content=ErrorResponse(error=error).model_dump(),
                status_code=500,
            )
        return {"status": "success"}

    return router
