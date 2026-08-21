from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from database import posts
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.posts import CreatePostRequest, UpdatePostRequest


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/{jurisdiction_ocdid:path}")
    async def create_post_endpoint(
        jurisdiction_ocdid: str,
        body: CreatePostRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Create a seat. 409 if the triple is taken — silently returning the existing id
        would make "created" and "already there" indistinguishable."""
        post_id = await posts.create(
            jurisdiction_ocdid,
            body.role_id,
            body.division_ocdid,
            body.label,
            body.headcount,
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
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        if not await posts.update(post_id, body.label, body.headcount):
            return JSONResponse({"error": "No such post."}, status_code=404)
        return {"data": {"ok": True}}

    @router.delete("/{post_id}")
    async def delete_post_endpoint(
        post_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Remove a post nobody has ever held — what is deletable is exactly what no person
        has endorsed."""
        if not await posts.delete(post_id):
            return JSONResponse(
                {"error": "No such post, or it has members and is history."},
                status_code=409,
            )
        return {"data": {"ok": True}}

    @router.get("/{jurisdiction_ocdid:path}")
    async def get_posts_endpoint(
        jurisdiction_ocdid: str,
        as_of: date | None = None,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED)),
    ):
        """Every body in a jurisdiction with its posts, grouped for the roster screen.

        `:path` because an ocdid contains slashes. **Declared last** so `/{post_id}` routes
        match before this swallows them.

        `?as_of=YYYY-MM-DD` gives the holders on that date, defaulting to now. Everything is
        returned either way; `_verified` on each row says whether a person vouched for it.
        """
        return {
            "data": {
                "organizations": await posts.list_by_organization(
                    jurisdiction_ocdid, as_of
                )
            }
        }

    return router
