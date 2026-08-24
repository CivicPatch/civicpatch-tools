from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from database import assertions
from database.change_logs import record_change
from database.database import get_pool
from lib.auth import require_route_access
from schemas.assertions import Assertion
from schemas.change_logs import AssertionChangePayload
from schemas.common import Identity, RouteCategory, UserRole
from shared.utils.statuses import ChangeLogType


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("")
    async def create_assertion_endpoint(
        body: Assertion,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Accept or reject one field value directly, rather than by editing a row.

        The only path that carries `sources` — "phoned the clerk, there really are five
        trustees" exists nowhere else — and the only one that reaches a scrape no publish can:
        a superseded request can never be published, so the rows most needing judgement had no
        way to receive it.

        401 rather than a NULL author: `assertions.asserted_by` is NOT NULL, because an
        assertion nobody made is not an assertion.
        """
        if not user.user_id:
            return JSONResponse(
                {"error": "Assertions must be attributable to a signed-in user."},
                status_code=401,
            )
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            assertion_id = await assertions.upsert(cur, body, user.user_id)
            # Logged in the same transaction, because an assertion is current state: setting a
            # field again overwrites it, and this is what keeps the superseded value.
            await record_change(
                cur,
                ChangeLogType.ASSERT_FIELD,
                user.user_id,
                changes=AssertionChangePayload(
                    entity_type=body.entity_type.value,
                    entity_id=body.entity_id,
                    field_path=body.field_path,
                    kind=body.kind.value,
                    value=body.value,
                    sources=[source.model_dump() for source in body.sources],
                ),
            )
            await conn.commit()
        return {"data": {"id": assertion_id}}

    return router
