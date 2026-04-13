from fastapi import APIRouter, Depends

from database.summary import get_summary_counts
from schemas.common import Identity, Role, RouteCategory
from lib.auth import require_route_access


def get_router():
    router = APIRouter()

    @router.get("")
    async def get_summary_endpoint(
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.CONTRIBUTORS, Role.MAINTAINERS])
        ),
    ):
        include_issues = "maintainers" in (user.teams or [])
        return await get_summary_counts(include_issues=include_issues)

    return router
