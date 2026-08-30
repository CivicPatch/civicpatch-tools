"""What a reviewer does with a card: approve it, reject it, save corrections, report an issue.

The reads are `review_cards.py`. Every handler here is thin — it turns a service exception into
a status code and nothing else; `services/roster_edits.py` owns what the actions mean.
"""

import logging
from typing import List

import database.issues
import database.people
import database.pipeline_runs
import database.review_session_entries as review_session_entries_db
import database.users
import services.review_issue_report as review_issue_report_service
import services.roster_edits as roster_edits
from database.publications import SupersededRoster
from core.people_edits import PeopleValidationError, PersonPatch
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from lib.auth import require_route_access
from pydantic import BaseModel
from schemas.common import (
    Identity,
    ReportReviewIssueRequest,
    RouteCategory,
    UserRole,
)
from services.publish import (
    dismiss_people,
)

logger = logging.getLogger(__name__)
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
    if isinstance(exc, SupersededRoster):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=409, detail=MISSING_ROSTER_DETAIL)


# ──────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────



def get_router(api_key_header):
    router = APIRouter()

    # -- File an issue against this scrape ---
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

    # -- Reject: settle the scrape without publishing ---
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

    # -- Save updates: record the reviewer's corrections, publish nothing ---
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

    # -- Approve: make this roster the published one ---
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
        except (
            roster_edits.MissingRoster,
            roster_edits.AnonymousEdit,
            PeopleValidationError,
            SupersededRoster,
        ) as exc:
            raise _http_error(exc)
        await review_session_entries_db.resolve_entries_for_request(request.request_id)
        return {"status": "published"}

    return router
