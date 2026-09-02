import math
import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from database import posts
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory
from schemas.posts import CreatePostRequest, UpdatePostRequest


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/{jurisdiction_ocdid:path}")
    async def create_post_endpoint(
        jurisdiction_ocdid: str,
        body: CreatePostRequest,
        # Any signed-in user: a reviewer who knows somebody sits in District 4 cannot say so
        # unless that post exists, and the post select offers only what already does. Their
        # changes land in the quarantine bucket like every other default-role write.
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        """Create a post. 409 if the triple is taken — silently returning the existing id
        would make "created" and "already there" indistinguishable."""
        post_id = await posts.create(
            jurisdiction_ocdid,
            body.role_id,
            body.division_ocdid,
            body.headcount,
            user.user_id,
        )
        if post_id is None:
            return JSONResponse(
                {"error": "A post already exists for that role and division."},
                status_code=409,
            )
        return {"data": {"id": post_id}}

    @router.patch("/{post_id}")
    async def update_post_endpoint(
        post_id: str,
        body: UpdatePostRequest,
        user: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        if not await posts.update(
            post_id, body.headcount, body.is_tracked, user.user_id
        ):
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
            state.lower(), per_page, (page - 1) * per_page
        )
        return {
            "total_items": total,
            "page": page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
            "data": rows,
        }

    @router.get("/{jurisdiction_ocdid:path}")
    async def get_posts_endpoint(jurisdiction_ocdid: str):
        """Every body in a jurisdiction with its posts, grouped for the roster screen.

        Unauthenticated, like the people and role reads: this is the jurisdiction page's own
        data, and that page is public. Every write below is gated on its own.

        `:path` because an ocdid contains slashes. **Declared last** so `/{post_id}` routes
        match before this swallows them.

        Undated: a post is not a temporal fact, and who holds one at a given moment is the
        memberships read. `_is_verified` on each row says whether a person vouched for it.
        """
        return {
            "data": {"organizations": await posts.list_by_organization(jurisdiction_ocdid)}
        }

    return router
