from datetime import date

from database import memberships
from services import membership_assertions
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory
from schemas.pagination import pagination_offset, pagination_total_pages
from schemas.posts import MembershipRemovalRequest


def get_router() -> APIRouter:
    router = APIRouter()

    # One endpoint, not four: the three claims contradict each other, so the request names which
    # one is being made and the service withdraws the others. Reversible by picking `none` again,
    # which is why any signed-in user may claim it while deleting a person (people.py) is
    # maintainers-only.
    @router.put("/{membership_id}/assertion")
    async def set_membership_assertion_endpoint(
        membership_id: str,
        body: MembershipRemovalRequest,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        # 401 rather than a NULL author, as `routers/api/assertions.py`: a claim nobody made is
        # not a claim, and `assertions.created_by` is NOT NULL.
        if not user.user_id:
            return JSONResponse(
                {"error": "Assertions must be attributable to a signed-in user."},
                status_code=401,
            )
        await membership_assertions.set_assertion(
            membership_id, body.assertion, user.user_id, body.reason, body.changeset_id
        )
        return {"data": {"ok": True}}

    @router.get("/unmatched")
    async def unmatched_text_endpoint(
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED)),
    ):
        total, rows = await memberships.meta_unmatched_text(per_page, pagination_offset(page, per_page))
        return {
            "data": {"meta_unmatched_text": rows},
            "total_items": total,
            "page": page,
            "total_pages": pagination_total_pages(total, per_page),
        }

    # Declared after `/unmatched` — `:path` matches greedily, so the reverse order would make
    # this swallow it and read "unmatched" as a jurisdiction ocdid.
    @router.get("/{jurisdiction_ocdid:path}")
    async def list_memberships_endpoint(
        jurisdiction_ocdid: str,
        as_of: date | None = None,
    ):
        return {
            "data": {
                "memberships": await memberships.list_by_person(
                    jurisdiction_ocdid, as_of
                )
            }
        }

    return router
