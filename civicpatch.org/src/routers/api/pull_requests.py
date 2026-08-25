import asyncio
import json
import logging
import os
from typing import List, Optional

import database.issues
import database.jurisdictions as jurisdictions_db
import database.people
import database.pipeline_runs
import database.pull_requests as pull_requests_db
import database.review_session_entries as review_session_entries_db
import database.users
import lib.buckets as buckets
import lib.redis as redis_store
import lib.storage as storage_service
import services.review_issue_report as review_issue_report_service
import services.roster_edits as roster_edits
import shared.utils.data_path_utils
import shared.utils.id_utils
import shared.utils.url_utils
from core.people_edits import PeopleValidationError, PersonPatch
from database.people import DEFAULT_VIEW, VIEWS
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from pydantic import BaseModel
from schemas.common import (
    Identity,
    ReportReviewIssueRequest,
    ReviewMode,
    RouteCategory,
    UserRole,
)
from services.publish import (
    dismiss_people,
)
from services.review_proposal import (
    assertions_for_people,
    proposals_for_requests,
    review_summary_for_request,
)
import services.roster as services_roster
from services.roster import proposed_roster

logger = logging.getLogger(__name__)


def _source_url_to_markdown_url(
    request_id: str, jurisdiction_ocdid_folder: str, source_url: str
) -> Optional[str]:
    source_url_dir = shared.utils.url_utils.format_url_to_folder(source_url)
    relative_path = os.path.join(
        request_id,
        "data_source",
        jurisdiction_ocdid_folder,
        "cache",
        source_url_dir,
        "preprocessed.md",
    )
    return storage_service.get_presigned_url_cached(buckets.DEBUG, relative_path)


def build_sources(
    request_id: str, jurisdiction_ocdid: str, source_urls: list[str]
) -> list[dict]:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return [
        {"url": url, "markdown": _source_url_to_markdown_url(request_id, folder, url)}
        for url in source_urls
    ]


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


# A scrape that recorded no sightings has nothing to review: the roster is derived from them,
# so there is no other copy to fall back to.
MISSING_ROSTER_DETAIL = "This scrape recorded no roster. Re-run it before reviewing."


# The service raises what went wrong; the status code is this layer's business. `patch_people`
# raises `PeopleValidationError` straight through — a 422 carrying which fields failed.
def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PeopleValidationError):
        return HTTPException(status_code=422, detail=exc.failures)
    if isinstance(exc, roster_edits.AnonymousEdit):
        return HTTPException(status_code=401, detail="Sign in to record an edit.")
    return HTTPException(status_code=409, detail=MISSING_ROSTER_DETAIL)


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
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        pull_requests, _, _ = await pull_requests_db.list_open_pull_requests(
            jurisdiction_ocdid=jurisdiction_ocdid
        )
        return {"data": pull_requests}

    # ── Pull Requests: List & Data ───────────
    @router.get(
        "/data",
        summary="The roster a scrape proposes, beside the one that is published",
    )
    async def get_pull_request_data_endpoint(
        jurisdiction_ocdid: str,
        request_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        existing, proposed = await asyncio.gather(
            database.people.get_people(
                jurisdiction_ocdid=jurisdiction_ocdid,
                status=database.people.ACTIVE_STATUS,
            ),
            proposed_roster(request_id, jurisdiction_ocdid),
        )
        if not proposed:
            return JSONResponse(
                content={"error": MISSING_ROSTER_DETAIL}, status_code=404
            )

        return {
            "request_id": request_id,
            "file_path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(
                jurisdiction_ocdid
            ),
            "data": proposed,
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
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        (
            paged_pull_requests,
            total,
            with_issues,
        ) = await pull_requests_db.list_open_pull_requests(
            state_code=state_code,
            jurisdiction_ocdid=jurisdiction_ocdid,
            page=page,
            per_page=per_page,
        )
        total_pages = (total + per_page - 1) // per_page

        jurisdiction_ocdids = list(
            {
                pr["jurisdiction"]["ocdid"]
                for pr in paged_pull_requests
                if pr.get("jurisdiction")
            }
        )
        request_ids = list({pr["request_id"] for pr in paged_pull_requests})
        published, rosters, proposals = await asyncio.gather(
            database.people.get_people_by_jurisdictions(jurisdiction_ocdids, view=view),
            services_roster.proposed_rosters(request_ids),
            # What each scrape would actually change. `existing` and `proposed` are two rosters
            # a reader has to diff by eye; this is the diff.
            proposals_for_requests(request_ids),
        )

        results = []
        for pr in paged_pull_requests:
            proposed = [
                database.people.projected(person, view)
                for person in rosters.get(pr["request_id"], [])
            ]
            unique_source_urls = list(
                {
                    url
                    for person in proposed
                    for url in (person.get("source_urls") or [])
                }
            )
            results.append(
                {
                    **pr,
                    "existing": published.get(pr["jurisdiction"]["ocdid"], []),
                    "proposed": proposed,
                    "changes": [
                        change.model_dump()
                        for change in proposals.get(pr["request_id"], [])
                    ],
                    "sources": build_sources(
                        pr["request_id"],
                        pr["jurisdiction"]["ocdid"],
                        unique_source_urls,
                    ),
                }
            )
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
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        result = await pull_requests_db.get_pull_request_data_by_request_id(request_id)
        if not result:
            raise HTTPException(status_code=404, detail="Pull request not found")

        request_id = result["request_id"]
        jurisdiction_ocdid = result["jurisdiction_ocdid"]

        existing, proposed, scraped_at, proposals = await asyncio.gather(
            database.people.get_people(
                jurisdiction_ocdid=jurisdiction_ocdid,
                status=database.people.ACTIVE_STATUS,
            ),
            proposed_roster(request_id, jurisdiction_ocdid),
            jurisdictions_db.get_scraped_at(jurisdiction_ocdid),
            # What this scrape would change about who holds what. The queue listing has carried
            # it since the proposal landed; the review session reads this endpoint instead, and
            # without it a proposed person has no post to name — the post does not exist yet, so
            # the derivation is the only thing that knows.
            proposals_for_requests([request_id]),
        )
        unique_source_urls = list(
            {url for person in proposed for url in (person.get("source_urls") or [])}
        )

        return {
            "data": {
                "request_id": request_id,
                "entry_number": 1,
                "has_next": False,
                "has_prev": False,
                "jurisdiction": {
                    "ocdid": jurisdiction_ocdid,
                    "name": result["jurisdiction_name"],
                    "path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(
                        jurisdiction_ocdid
                    ),
                    "website_url": result["jurisdiction_website_url"],
                },
                "pr": result["pr"],
                "mode": ReviewMode.for_scrape(scraped_at).value,
                "existing": existing,
                "proposed": proposed,
                "changes": [
                    change.model_dump() for change in proposals.get(request_id, [])
                ],
                "assertions": await assertions_for_people(
                    [person["id"] for person in existing if person.get("id")]
                ),
                "sources": build_sources(
                    request_id, jurisdiction_ocdid, unique_source_urls
                ),
            }
        }

    # -- Pull Requests: Issues for a job ---
    @router.get("/{request_id}/review")
    async def get_pull_request_review_endpoint(
        request_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        return {"data": await review_summary_for_request(request_id)}

    # -- Pull Requests: Reviewer-filed issues for this request ---
    @router.get("/{request_id}/issues")
    async def get_reported_issues_endpoint(
        request_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        result = await database.issues.get_user_reported_issues_for_request(request_id)
        return {"data": result}

    # -- Pull Requests: Report an issue on open-data ---
    @router.post("/{request_id}/issues")
    async def report_review_issue_endpoint(
        request_id: str,
        body: ReportReviewIssueRequest,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
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
        user_id = await database.users.get_user_id_by_provider(
            user.provider, user.provider_user_id
        )
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
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        try:
            await roster_edits.save(
                request.request_id, request.jurisdiction_ocdid, request.data, user
            )
        except (roster_edits.MissingRoster, roster_edits.AnonymousEdit, PeopleValidationError) as exc:
            raise _http_error(exc)
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
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        edited = None
        try:
            if request.data:
                edited = await roster_edits.save(
                    request.request_id, request.jurisdiction_ocdid, request.data, user
                )

            if not user.user_id:
                raise HTTPException(status_code=401, detail="User ID not available")

            # Publishing is a database write, so it is synchronous: a 200 means the roster is
            # live and `published_at` is stamped. The open-data commit is queued behind it and
            # retries on its own — git is the projection, not the record.
            await roster_edits.publish(
                request.request_id, request.jurisdiction_ocdid, edited, user.user_id
            )
        except (roster_edits.MissingRoster, roster_edits.AnonymousEdit, PeopleValidationError) as exc:
            raise _http_error(exc)
        await review_session_entries_db.resolve_entries_for_request(request.request_id)
        return {"status": "published"}

    # -- Pull Requests: Merge Status ---
    @router.get("/{pull_request_number}/merge-status", include_in_schema=False)
    async def merge_status_endpoint(
        pull_request_number: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        raw = await redis_store.get(f"merge_status:{pull_request_number}")
        if not raw:
            return {"status": "pending"}
        return json.loads(raw)

    return router
