import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from psycopg.errors import UniqueViolation
from pydantic import BaseModel

import database.people
import database.review_sessions as review_sessions_db
from database.database import get_pool
from schemas.common import Identity, Role, RouteCategory
from utils.auth_utils import require_route_access

logger = logging.getLogger(__name__)


class CreateReviewSessionRequest(BaseModel):
    state_code: str
    daily_goal: Optional[int] = None


def get_router() -> APIRouter:
    router = APIRouter()

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
        if result is None:
            return {"data": None}

        current_entry = result.get("current_entry")
        if current_entry:
            current_entry = await _enrich_entry(current_entry)

        return {"data": {**result, "current_entry": current_entry}}

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

    @router.post("/{session_id}/next")
    async def advance_session(
        session_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        result = await _advance_with_retry(session_id)
        if result is None:
            return {"data": None}

        daily_goal = await _get_session_daily_goal(session_id)
        enriched = await _enrich_entry({"job": result["job"]})
        return {
            "data": {
                **enriched,
                "entry_number": result["entry_number"],
                "daily_goal": daily_goal,
            }
        }

    return router


async def _advance_with_retry(session_id: str):
    try:
        return await review_sessions_db.advance_review_session(session_id)
    except UniqueViolation:
        try:
            return await review_sessions_db.advance_review_session(session_id)
        except UniqueViolation:
            raise HTTPException(status_code=409, detail="Could not claim a jurisdiction; please try again")


async def _enrich_entry(entry: dict) -> dict:
    job = entry.get("job", {})
    jurisdiction_ocdid = job.get("jurisdiction_ocdid")
    request_id = job.get("request_id")
    if not jurisdiction_ocdid or not request_id:
        return entry

    people_data = await database.people.get_people_data_by_request_ids(
        [jurisdiction_ocdid], [request_id]
    )
    enriched = people_data.get(request_id, {})
    return {
        **entry,
        "job": job,
        "existing": enriched.get("existing", []),
        "pull_request": enriched.get("pull_request", []),
    }


async def _get_session_daily_goal(session_id: str) -> int:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT daily_goal FROM review_sessions WHERE id = %s",
                (session_id,),
            )
            row = await cur.fetchone()
    return row[0] if row else 10
