from datetime import date

from database import memberships
from fastapi import APIRouter, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.posts import AssignMembershipRequest
from services.publish import commit_roster


def get_router() -> APIRouter:
    router = APIRouter()

    @router.put("")
    async def assign_membership_endpoint(
        body: AssignMembershipRequest,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        try:
            result = await memberships.assign(
                body.person_id, body.post_id, body.label, user.user_id
            )
        except memberships.UnknownPost:
            return JSONResponse({"error": "No such post."}, status_code=404)
        except memberships.NothingToAssign:
            return JSONResponse(
                {"error": "They already hold that post under that label."},
                status_code=409,
            )
        # This edit mints no changeset, so nothing else will mirror it: without this the
        # database moves the seat and open-data drifts until the next real publish.
        # Backgrounded because the row is already committed — a Temporal outage must not
        # turn a successful assignment into a 500.
        background_tasks.add_task(
            commit_roster,
            result.jurisdiction_ocdid,
            f"Assign membership in {result.jurisdiction_ocdid}",
        )
        return {"data": result}

    @router.get("/unmatched")
    async def unmatched_text_endpoint(
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED)),
    ):
        offset = (page - 1) * per_page
        total, rows = await memberships.unmatched_text(per_page, offset)
        return {
            "data": {"unmatched_text": rows},
            "total_items": total,
            "page": page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
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
