import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database import posts
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.pagination import paginated_response, pagination_offset
from schemas.posts import UpdatePostRequest


def get_router() -> APIRouter:
    router = APIRouter()

    @router.patch("/{post_id}")
    async def update_post_endpoint(
        post_id: str,
        body: UpdatePostRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        jurisdiction_ocdid = await posts.update(
            post_id, body.headcount, body.is_tracked, user.user_id
        )
        if jurisdiction_ocdid is None:
            return JSONResponse({"error": "No such post."}, status_code=404)
        return {"data": {"ok": True}}

    @router.get("/bulk")
    async def bulk_posts_endpoint(
        state: str,
        page: int = Query(1, ge=1),
        per_page: int = Query(200, ge=1, le=500),
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        """Every post in a state, paged.

        One request per page instead of one per jurisdiction. Signed-in rather than public for
        the same reason as `/people/bulk`: the same rows are readable a jurisdiction at a time,
        but handing out a state in one call is a different thing to offer anonymously.
        """
        if not re.fullmatch(r"[A-Za-z]{2}", state):
            raise HTTPException(
                status_code=400, detail="state must be a two-letter code, e.g. 'wa'"
            )
        total, rows = await posts.list_page_for_state(
            state.lower(), per_page, pagination_offset(page, per_page)
        )
        return paginated_response(total, page, per_page, rows)

    return router
