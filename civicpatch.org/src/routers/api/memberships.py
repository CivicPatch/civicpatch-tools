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
        """Assign a person. Idempotent: re-assigning to the post they hold only sets the label.

        `moved_from` is the post they were closed off, or null — the caller needs it to say
        "moved from X" rather than "assigned", since a move leaves history behind.
        """
        try:
            result = await memberships.assign(
                body.person_id, body.post_id, body.label, user.user_id
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

    # Declared after `/unmatched` — `:path` matches greedily, so the reverse order would make
    # this swallow it and read "unmatched" as a jurisdiction ocdid.
    @router.get("/{jurisdiction_ocdid:path}")
    async def list_memberships_endpoint(
        jurisdiction_ocdid: str,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED)),
    ):
        """The same roster the posts read returns, by person instead of by post.

        Open memberships only: this answers "who sits where now". The dated question is
        `?as_of` on the posts read, which is the axis a date makes sense on.
        """
        return {
            "data": {
                "memberships": await memberships.list_by_person(jurisdiction_ocdid)
            }
        }

    return router
