"""Reading a scrape awaiting review: the queue, and one card in it.

Nothing here writes. What a reviewer *does* with a card is `review_actions.py` — they share a
prefix because they are one surface to the frontend, and are separate files because a read
that can only 404 and a write that publishes to open-data fail in very different ways.
"""

import asyncio
import logging
from typing import List

import database.issues
import database.jurisdictions as jurisdictions_db
import database.people
import database.pipeline_runs
import database.review_pool as review_pool_db
import database.users
import services.roster_edits as roster_edits
import shared.utils.data_path_utils
import shared.utils.id_utils
import shared.utils.url_utils
from core.people_edits import PeopleValidationError, PersonPatch
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from pydantic import BaseModel
from schemas.review_cards import ReviewCard
from schemas.common import (
    Identity,
    ReviewMode,
    RouteCategory,
    UserRole,
    has_at_least,
)
from services.review_proposal import (
    assertions_for_people,
    proposals_for_requests,
    review_summary_for_changeset,
)
import services.review_cards as review_cards_service
from services.review_sources import build_sources, without_debug_links
from services.roster import proposed_roster, proposed_roster_and_source_values

logger = logging.getLogger(__name__)
# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────


class SaveAndMergeRequest(BaseModel):
    changeset_id: str
    jurisdiction_ocdid: str
    data: List[PersonPatch] | None = None


class SaveReviewRequest(BaseModel):
    changeset_id: str
    jurisdiction_ocdid: str
    data: List[PersonPatch]


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class DeleteJobResponse(BaseModel):
    changeset_id: str
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



def _for_viewer(cards: list[ReviewCard], viewer_role: str | None) -> list[ReviewCard]:
    """Everyone keeps each card's sources; only admins get the debug bucket's copies of them."""
    if has_at_least(viewer_role, UserRole.ADMINS):
        return cards
    return [
        card.model_copy(
            update={
                "sources": [
                    source.model_copy(update={"markdown": None, "html": None})
                    for source in card.sources
                ]
            }
        )
        for card in cards
    ]


def get_router(api_key_header):
    router = APIRouter()

    # -- Cards awaiting review in one jurisdiction ---
    # Unpaged: the jurisdiction detail page shows these above the roster, and a place has at
    # most a handful of scrapes stacked up.
    @router.get(
        "",
        summary="List open pull requests",
    )
    async def list_pull_requests_endpoint(
        jurisdiction_ocdid: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        pull_requests, _, _ = await review_pool_db.list_open_changesets(
            jurisdiction_ocdid=jurisdiction_ocdid
        )
        return {"data": pull_requests}

    # -- One card: the proposed roster beside the published one ---
    @router.get(
        "/data",
        summary="The roster a scrape proposes, beside the one that is published",
    )
    async def get_pull_request_data_endpoint(
        jurisdiction_ocdid: str,
        changeset_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        existing, proposed = await asyncio.gather(
            database.people.get_roster(jurisdiction_ocdid=jurisdiction_ocdid),
            proposed_roster(changeset_id, jurisdiction_ocdid),
        )
        if not proposed:
            return JSONResponse(
                content={"error": MISSING_ROSTER_DETAIL}, status_code=404
            )

        return {
            "changeset_id": changeset_id,
            "file_path": shared.utils.id_utils.jurisdiction_ocdid_to_folder(
                jurisdiction_ocdid
            ),
            "data": proposed,
            "existing": existing,
        }

    # -- A page of cards, both rosters and the diff for each ---
    @router.get(
        "/with-data",
        summary="Batch get pull request details and data",
    )
    async def get_pull_requests_with_data(
        page: int = 1,
        per_page: int = 10,
        state_code: str | None = None,
        jurisdiction_ocdid: str | None = None,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        (
            paged_pull_requests,
            total,
            with_issues,
        ) = await review_pool_db.list_open_changesets(
            state_code=state_code,
            jurisdiction_ocdid=jurisdiction_ocdid,
            page=page,
            per_page=per_page,
        )
        total_pages = (total + per_page - 1) // per_page
        cards = _for_viewer(
            await review_cards_service.with_card_data(
                [pr["changeset_id"] for pr in paged_pull_requests]
            ),
            user.role,
        )
        # Flat, as this endpoint has always answered: the listing row with the card beside it.
        results = [
            {**pr, **card.model_dump()} for pr, card in zip(paged_pull_requests, cards)
        ]
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

    # -- Any cards, by changeset: what a page listing its own selection loads ---
    @router.get("/cards", summary="Review cards for the given changesets, in that order")
    async def get_cards_endpoint(
        changeset_ids: List[str] = Query(...),
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        return {
            "data": _for_viewer(
                await review_cards_service.with_card_data(changeset_ids), user.role
            )
        }

    # -- One card by deep link, the shape a review session navigates ---
    @router.get("/by-request/{changeset_id}")
    async def get_pull_request_by_changeset_id_endpoint(
        changeset_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        result = await review_pool_db.get_changeset_data(changeset_id)
        if not result:
            raise HTTPException(status_code=404, detail="Pull request not found")

        changeset_id = result["changeset_id"]
        jurisdiction_ocdid = result["jurisdiction_ocdid"]

        existing, (proposed, overridden), has_ever_collected, proposals = await asyncio.gather(
            database.people.get_roster(jurisdiction_ocdid=jurisdiction_ocdid),
            proposed_roster_and_source_values(changeset_id, jurisdiction_ocdid),
            jurisdictions_db.has_ever_collected(jurisdiction_ocdid),
            # What this scrape would change about who holds what. The queue listing has carried
            # it since the proposal landed; the review session reads this endpoint instead, and
            # without it a proposed person has no post to name — the post does not exist yet, so
            # the derivation is the only thing that knows.
            proposals_for_requests([changeset_id]),
        )
        unique_source_urls = list(
            {url for person in proposed for url in (person.get("source_urls") or [])}
        )
        sources = build_sources(changeset_id, jurisdiction_ocdid, unique_source_urls)
        if not has_at_least(user.role, UserRole.ADMINS):
            sources = without_debug_links(sources)

        return {
            "data": {
                "changeset_id": changeset_id,
                "entry_number": 1,
                "has_next": False,
                "has_prev": False,
                "jurisdiction": {
                    "ocdid": jurisdiction_ocdid,
                    "name": result["jurisdiction_name"],
                    "path": jurisdiction_ocdid,
                    "website_url": result["jurisdiction_website_url"],
                },
                "pr": result["pr"],
                "mode": ReviewMode.for_scrape(has_ever_collected).value,
                "existing": existing,
                "proposed": proposed,
                "changes": [
                    change.model_dump() for change in proposals.get(changeset_id, [])
                ],
                "assertions": await assertions_for_people(
                    [person["id"] for person in existing if person.get("id")]
                ),
                # See the same key on the session endpoint: the fields an assertion changed,
                # with what the source had said.
                "overridden_source_values": overridden,
                "sources": sources,
            }
        }

    # -- The review summary: stored issues plus the ones computed from posts ---
    @router.get("/{changeset_id}/review")
    async def get_pull_request_review_endpoint(
        changeset_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        return {"data": await review_summary_for_changeset(changeset_id)}

    # -- Issues a reviewer filed by hand on this scrape ---
    @router.get("/{changeset_id}/issues")
    async def get_reported_issues_endpoint(
        changeset_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        result = await database.issues.get_user_reported_issues_for_changeset(changeset_id)
        return {"data": result}

    return router
