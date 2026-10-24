import re

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

import services.roster_edits as roster_edits
from database import post_listings, posts
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
        assert user.user_id is not None
        jurisdiction_ocdid = await posts.update(
            post_id, body.meta_headcount, user.user_id
        )
        if jurisdiction_ocdid is None:
            return JSONResponse({"error": "No such post."}, status_code=404)
        return {"data": {"ok": True}}

    @router.delete("/{post_id}", include_in_schema=False)
    async def delete_post_endpoint(
        post_id: str,
        into: str | None = Query(None, description="The post to move this post's memberships to"),
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Delete a post. One somebody holds needs `into`: the same role and division in another
        organization, which takes its memberships."""
        assert user.user_id is not None
        if into is None:
            try:
                deleted = await posts.delete(post_id, user.user_id)
            except posts.PostHasMembers as exc:
                return JSONResponse(
                    {"error": "Somebody holds or held this post; pick a post to move them to."},
                    status_code=409,
                )
            if not deleted:
                return JSONResponse({"error": "No such post."}, status_code=404)
            return {"data": {"changeset_id": None}}
        try:
            changeset_id = await roster_edits.delete_post_into(post_id, into, user.user_id)
        except roster_edits.UnknownPost:
            return JSONResponse({"error": "No such post."}, status_code=404)
        except roster_edits.PostMergeRefused as exc:
            return JSONResponse({"error": str(exc)}, status_code=422)
        except posts.PostHasMembers:
            return JSONResponse(
                {"error": "The move did not empty this post, so it was not deleted."},
                status_code=409,
            )
        return {"data": {"changeset_id": changeset_id}}

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
        total, rows = await post_listings.list_page_for_state(
            state.lower(), per_page, pagination_offset(page, per_page)
        )
        return paginated_response(total, page, per_page, rows)

    return router
