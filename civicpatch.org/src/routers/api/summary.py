from typing import Optional

from fastapi import APIRouter, Depends

from database.summary import get_summary_counts
from schemas.common import Identity, Role, RouteCategory, has_at_least
from lib.auth import require_route_access


def get_router():
    router = APIRouter()

    @router.get("")
    async def get_summary_endpoint(
        state_code: Optional[str] = None,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, Role.CONTRIBUTORS)
        ),
    ):
        include_issues = has_at_least(user.role, Role.MAINTAINERS)
        return await get_summary_counts(include_issues=include_issues, state_code=state_code)

    return router
