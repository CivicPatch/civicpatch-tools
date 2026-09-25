from datetime import date

from database import memberships
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory
from schemas.pagination import pagination_offset, pagination_total_pages


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/unmatched", include_in_schema=False)
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
