"""Changeset activity across every state.

`/api/internal/` because the response is shaped for this page and the frontend is its only
consumer.

Signed-in, matching the rest of the Activity section: these are counts of changesets whose
underlying rows are already public on each jurisdiction page. Starting a scrape from this data
is a separate, Maintainer-gated action.
"""

import logging

from database import changeset_summaries as db
from fastapi import APIRouter, Depends, HTTPException, Query
from lib.auth import require_route_access
from schemas.common import RouteCategory

logger = logging.getLogger(__name__)

# Bounded: an unbounded window is an unbounded scan for anyone editing the query string.
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 365

MAX_BUCKET_PAGE = 200

VALID_BUCKETS = (
    db.BUCKET_REVIEW,
    db.BUCKET_DISMISSED,
    db.BUCKET_PUBLISHED,
    db.BUCKET_FAILED_RUNS,
)


def get_router() -> APIRouter:
    router = APIRouter(
        dependencies=[Depends(require_route_access(RouteCategory.AUTHENTICATED))]
    )

    @router.get("/rollup")
    async def get_state_rollup_endpoint(
        window_days: int = Query(
            db.DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS
        ),
    ):
        return {"data": await db.get_state_rollup(window_days)}

    @router.get("/calendar")
    async def get_state_calendar_endpoint(
        window_days: int = Query(
            db.DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS
        ),
    ):
        return {"data": await db.get_state_calendar(window_days)}

    @router.get("/buckets/{state}/{bucket}")
    async def get_state_bucket_endpoint(
        state: str,
        bucket: str,
        limit: int = Query(50, ge=1, le=MAX_BUCKET_PAGE),
        offset: int = Query(0, ge=0),
        window_days: int = Query(
            db.DEFAULT_WINDOW_DAYS, ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS
        ),
    ):
        # 404, not an empty page — the query fails closed, so a typo would read as "nothing
        # here" and send someone away from work that exists.
        if bucket not in VALID_BUCKETS:
            raise HTTPException(status_code=404, detail=f"No such bucket: {bucket}")
        return {"data": await db.get_state_bucket(state, bucket, limit, offset, window_days)}

    return router
