import asyncio
import logging
from typing import Optional

import database.jurisdictions as jurisdictions_db
import database.people as database_people
import database.review_pool as review_pool_db
import database.review_session_entries as review_session_entries_db
import database.review_session_navigation as review_session_navigation_db
import database.review_session_stats as review_session_stats_db
import database.review_sessions as review_sessions_db
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import require_route_access
from psycopg.errors import UniqueViolation
from pydantic import BaseModel
from schemas.common import Identity, ReviewMode, RouteCategory
from services.review_proposal import assertions_for_people, proposals_for_requests
from services.review_sources import build_sources
from services.roster import proposed_roster
logger = logging.getLogger(__name__)


class CreateReviewSessionRequest(BaseModel):
    state_code: str
    daily_goal: Optional[int] = None


class NavigateToEntryRequest(BaseModel):
    entry_number: int


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/stats")
    async def get_review_stats(
        state_code: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")
        stats = await review_session_stats_db.get_review_stats(user.user_id, state_code)
        return {"data": stats}

    @router.post("")
    async def create_review_session(
        body: CreateReviewSessionRequest,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")
        session = await review_sessions_db.create_or_get_review_session(
            user.user_id,
            body.state_code,
            body.daily_goal,
        )
        return {"data": session}

    @router.post("/{session_id}/navigate")
    async def navigate_session(
        session_id: str,
        body: NavigateToEntryRequest,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        return await _navigate_response(session_id, body.entry_number)

    @router.post("/{session_id}/pass")
    async def pass_session(
        session_id: str,
        body: NavigateToEntryRequest,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        await review_session_entries_db.pass_entry(session_id, body.entry_number)
        return await _navigate_response(session_id, body.entry_number)

    @router.get("/active")
    async def get_active_session(
        state_code: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")
        session = await review_sessions_db.get_active_review_session(
            user.user_id, state_code
        )
        return {"data": session}

    @router.post("/{session_id}/end")
    async def end_session(
        session_id: str,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        await review_sessions_db.end_review_session(session_id)
        return {"data": None}

    return router


async def _navigate_response(session_id: str, entry_number: int):
    try:
        result = await review_session_navigation_db.navigate_to_entry(
            session_id, entry_number
        )
    except UniqueViolation:
        try:
            result = await review_session_navigation_db.navigate_to_entry(
                session_id, entry_number
            )
        except UniqueViolation:
            raise HTTPException(
                status_code=409,
                detail="Could not claim a jurisdiction; please try again",
            )
    if result is None:
        raise HTTPException(status_code=404)
    if "done" in result:
        # Exhausted session: end it now so a later /active lookup can't resurrect
        # it as resumable once the user has navigated past every entry.
        await review_sessions_db.end_review_session(session_id)
        return {"data": None, "reason": result["done"]}

    changeset_id = result["changeset_id"]
    jurisdiction_ocdid = result["jurisdiction_ocdid"]

    pr_meta, existing, proposed, scraped_at = await asyncio.gather(
        review_pool_db.get_changeset_for_review(changeset_id),
        database_people.get_roster(jurisdiction_ocdid=jurisdiction_ocdid),
        proposed_roster(changeset_id, jurisdiction_ocdid),
        jurisdictions_db.get_scraped_at(jurisdiction_ocdid),
    )

    # This is the endpoint a review session actually navigates through — `by-request` serves
    # deep links. Both need it, because a proposed person holds no membership yet and the
    # derivation is the only thing that knows which post they would land in.
    proposals = await proposals_for_requests([changeset_id])
    unique_source_urls = list(
        {url for person in proposed for url in (person.get("source_urls") or [])}
    )
    sources = build_sources(changeset_id, jurisdiction_ocdid, unique_source_urls)

    if pr_meta is None:
        raise HTTPException(status_code=404, detail="Pull request metadata not found")
    return {
        "data": {
            "changeset_id": changeset_id,
            "entry_number": result["entry_number"],
            "total": result["total"],
            "goal": result["goal"],
            "resolved_count": result["resolved_count"],
            "has_next": result.get("has_next", False),
            "jurisdiction": pr_meta["jurisdiction"],
            "pr": pr_meta["pr"],
            "mode": ReviewMode.for_scrape(scraped_at).value,
            "existing": existing,
            "proposed": proposed,
            "changes": [
                change.model_dump() for change in proposals.get(changeset_id, [])
            ],
            # Both sides: a reviewer's edit is asserted against the *proposed* person, who is
            # not in `existing` until they publish — so tagging only published ids would hide
            # a saved edit the moment the page reloads.
            "assertions": await assertions_for_people(
                list(
                    {
                        person["id"]
                        for person in existing + proposed
                        if person.get("id")
                    }
                )
            ),
            "sources": sources,
        }
    }
