import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg.errors import UniqueViolation
from pydantic import BaseModel

import database.review_sessions as review_sessions_db
from schemas.common import Identity, Role, RouteCategory
from utils.auth_utils import require_route_access

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
        stats = await review_sessions_db.get_review_stats(
            user.provider, user.provider_user_id, state_code
        )
        return {"data": stats}

    @router.get("/today")
    async def get_today_session(
        state_code: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        result = await review_sessions_db.get_today_session_with_current_entry(
            user.provider, user.provider_user_id, state_code
        )
        return {"data": result}

    @router.post("")
    async def create_review_session(
        body: CreateReviewSessionRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        session = await review_sessions_db.create_or_get_review_session(
            user.provider,
            user.provider_user_id,
            date.today(),
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
        await review_sessions_db.pass_current_entry(session_id)
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
    return {"data": result}
