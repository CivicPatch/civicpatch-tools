from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from database import assertions
from lib.auth import require_route_access
from schemas.assertions import Assertion
from schemas.common import Identity, RouteCategory, UserRole


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("")
    async def create_assertion_endpoint(
        body: Assertion,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Record that a person confirmed, corrected or retracted something.

        One endpoint for all three because they are one act — a human asserting something
        about a row, with sources. They differ only by whether a replacement value comes along.

        The case this exists for is the one no publish can reach: a scrape that was superseded
        can never be published, so the rows most needing human judgement had no way to receive
        it. Confirming reaches them directly.

        401 rather than a NULL author: `assertions.asserted_by` is NOT NULL, because an
        assertion nobody made is not an assertion.
        """
        if not user.user_id:
            return JSONResponse(
                {"error": "Assertions must be attributable to a signed-in user."},
                status_code=401,
            )
        assertion_id = await assertions.create(body, user.user_id)
        return {"data": {"id": assertion_id}}

    return router
