from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

import services.posts as posts_service
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
        """Create a seat. 409 if the identity triple is already taken.

        A duplicate is not an error to hide: the caller wants that post, and the answer is
        either to raise its headcount or to give one of them a label. Silently returning the
        existing id would make "created" and "already there" indistinguishable.
        """
        post_id = await posts_service.create(
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
        if not await posts_service.update(post_id, body.label, body.headcount):
            return JSONResponse({"error": "No such post."}, status_code=404)
        return {"data": {"ok": True}}

    @router.delete("/{post_id}")
    async def delete_post_endpoint(
        post_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Remove a post nobody has ever held.

        A post with memberships is history — including closed ones — so it stays. That is the
        same condition that reads as verified, so what is deletable is exactly what no person
        has endorsed.
        """
        if not await posts_service.delete(post_id):
            return JSONResponse(
                {"error": "No such post, or it has members and is history."},
                status_code=409,
            )
        return {"data": {"ok": True}}

    @router.get("/{jurisdiction_ocdid:path}")
    async def get_posts_endpoint(
        jurisdiction_ocdid: str,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED)),
    ):
        """Every body in a jurisdiction with its posts, grouped for the roster screen.

        `:path` because an ocdid contains slashes. Declared last so `/{post_id}` routes are
        matched before this swallows them.

        Internal rather than v1: this is the shape one screen renders, holder counts and all.
        A public posts surface is a separate decision — and would need the verified default,
        since an unverified post is a scrape's proposal, not a seat anyone has confirmed.
        """
        return {
            "data": {
                "organizations": await posts_service.list_for_jurisdiction(
                    jurisdiction_ocdid
                )
            }
        }

    return router
