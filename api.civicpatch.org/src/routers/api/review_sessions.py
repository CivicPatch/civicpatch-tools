import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg.errors import UniqueViolation
from pydantic import BaseModel

import database.review_sessions as review_sessions_db
import services.cache_service as cache_service
import services.github.pull_request_sync_service as pr_sync_service
from schemas.common import Identity, Role, RouteCategory
from utils.auth_utils import require_route_access

STATS_CACHE_TTL = 300  # 5 minutes

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
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        cache_key = f"review_stats:{user.user_id}:{state_code}"
        cached = await cache_service.get_cached(cache_key)
        if cached:
            cached.pop("expires_at", None)
            return {"data": cached}
        stats = await review_sessions_db.get_review_stats(
            user.user_id, state_code
        )
        await cache_service.set_cached(cache_key, stats, expires_at=time.time() + STATS_CACHE_TTL)
        return {"data": stats}

    @router.post("")
    async def create_review_session(
        body: CreateReviewSessionRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
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
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        return await _navigate_response(session_id, body.entry_number)

    @router.post("/{session_id}/pass")
    async def pass_session(
        session_id: str,
        body: NavigateToEntryRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        await review_sessions_db.pass_current_entry(session_id, body.entry_number)
        return await _navigate_response(session_id, body.entry_number)

    @router.post("/{session_id}/pause")
    async def pause_session(
        session_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        await review_sessions_db.pause_review_session(session_id)
        return {"data": None}

    return router


async def _navigate_response(session_id: str, entry_number: int):
    try:
        result = await review_sessions_db.navigate_to_entry(session_id, entry_number)
    except UniqueViolation:
        try:
            result = await review_sessions_db.navigate_to_entry(session_id, entry_number)
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="Could not claim a jurisdiction; please try again")
    if result is None:
        raise HTTPException(status_code=404)
    if "done" in result:
        return {"data": None, "reason": result["done"]}
    await pr_sync_service.sync_single_pr_state(result["request_id"])
    return {"data": result}
