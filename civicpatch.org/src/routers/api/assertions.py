from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from database import assertions
from database.activity import record_change
from database.changesets import live_roster_changeset
from database.database import get_pool
from database.entity_jurisdiction import jurisdiction_for, name_for
from lib.auth import require_route_access
from schemas.assertions import Assertion
from schemas.activity import Change, FieldChange
from schemas.common import Identity, RouteCategory, UserRole
from shared.utils.statuses import ActivityType


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

        401 rather than a NULL author: `assertions.created_by` is NOT NULL, because an
        assertion nobody made is not an assertion.
        """
        if not user.user_id:
            return JSONResponse(
                {"error": "Assertions must be attributable to a signed-in user."},
                status_code=401,
            )
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            jurisdiction_ocdid = await jurisdiction_for(
                cur, body.entity_type, body.entity_id
            )
            # Resolved once, and never taken from the client: `changeset_id` names which
            # changeset created this claim, so it has to be the server's own answer.
            changeset_id = (
                await live_roster_changeset(cur, jurisdiction_ocdid)
                if jurisdiction_ocdid
                else None
            )
            claim = body.model_copy(update={"changeset_id": changeset_id})
            assertion_id = await assertions.upsert(cur, claim, user.user_id)
            # Logged in the same transaction. The assertion row itself is the permanent record
            # now (187), but the activity feed still wants the narration alongside it.
            await record_change(
                cur,
                ActivityType.ASSERT_FIELD,
                user.user_id,
                jurisdiction_ocdid,
                changeset_id=changeset_id,
                changes=Change(
                    entity_type=body.entity_type,
                    entity_id=body.entity_id,
                    # Resolved here, once, rather than by every reader on every page load. The
                    # history used to look this up per row because an assertion payload carried
                    # only ids — and it is the one name that must be captured now, since the
                    # entity can be deleted before anybody reads the log.
                    subject=(
                        await name_for(cur, body.entity_type, body.entity_id)
                        or body.entity_type.value
                    ),
                    fields=[
                        FieldChange(
                            field=body.field_path,
                            after=body.value,
                            sources=[source.model_dump() for source in body.sources],
                        )
                    ],
                                ),
            )
            await conn.commit()
        return {"data": {"id": assertion_id}}

    return router
