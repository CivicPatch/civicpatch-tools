from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from database import memberships
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.posts import AssignMembershipRequest


def get_router() -> APIRouter:
    router = APIRouter()

    @router.put("")
    async def assign_membership_endpoint(
        body: AssignMembershipRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Seat a person. Idempotent: re-assigning to the seat they hold only sets the label.

        `moved_from` is the post they were closed off, or null — the caller needs it to say
        "moved from X" rather than "assigned", since a move leaves history behind.
        """
        try:
            result = await memberships.assign(
                body.person_id, body.post_id, body.label
            )
        except memberships.UnknownPost:
            return JSONResponse({"error": "No such post."}, status_code=404)
        return {"data": result}

    @router.get("/unmatched")
    async def unmatched_text_endpoint(
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED)),
    ):
        """Label text that matched neither the role aliases nor the designations, widest first.

        Not "a role we are missing" — the parser could not tell what kind of thing it is.

        Widest-spread first is the point: one curator needs the term that one rule change
        fixes everywhere, not the longest list.
        """
        return {"data": {"unmatched_text": await memberships.unmatched_text()}}

    return router
