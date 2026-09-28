from database import claims
from database.activity import record_change
from database.changesets import create_roster_edit_changeset
from database.database import get_pool
from database.entity_jurisdiction import jurisdiction_for, name_for
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from schemas.activity import Change, FieldChange
from schemas.claims import Claim, ClaimRequest
from schemas.common import Identity, RouteCategory, UserRole
from shared.utils.id_utils import make_id
from shared.utils.statuses import ActivityType


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("")
    async def create_claim_endpoint(
        body: ClaimRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Accept or reject one field value directly, rather than by editing a row.

        The only path that carries `sources` — "phoned the clerk, there really are five
        trustees" exists nowhere else — and the only one that reaches a scrape no publish can:
        a superseded request can never be published, so the rows most needing judgement had no
        way to receive it.

        401 rather than a NULL author: `claims.created_by` is NOT NULL, because an
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
            if not jurisdiction_ocdid:
                return JSONResponse(
                    {"error": f"No {body.entity_type.value} {body.entity_id}."},
                    status_code=404,
                )
            # Never taken from the client: it names the act that filed this claim.
            changeset_id = make_id()
            await create_roster_edit_changeset(
                cur, changeset_id, jurisdiction_ocdid, user.user_id
            )
            claim = Claim(**body.model_dump(), changeset_id=changeset_id)
            claim_id = await claims.upsert(cur, claim, user.user_id)
            # Logged in the same transaction. The claim row itself is the permanent record
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
        return {"data": {"id": claim_id}}

    return router
