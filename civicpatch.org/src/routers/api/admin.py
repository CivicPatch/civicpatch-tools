from fastapi import APIRouter, BackgroundTasks, Depends

import lib.cache as cache_service
import core.open_data_sync as data_sync
import core.pull_request_sync as pr_sync
from schemas.common import Identity, Role, RouteCategory
from schemas.open_data import OdSyncRequestSchema
from lib.auth import require_route_access

def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def od_sync_endpoint(
        request: OdSyncRequestSchema,
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS])),
    ):
        background_tasks.add_task(data_sync.sync, request)

        return {"status": "running"}

    @router.post("/pr_sync", include_in_schema=False)
    async def pr_sync_endpoint(
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS])),
    ):
        background_tasks.add_task(pr_sync.sync_open_pr_state)
        return {"status": "running"}

    @router.post("/clear_dashboard_cache", include_in_schema=False)
    async def clear_dashboard_cache_endpoint(
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS])),
    ):
        await cache_service.invalidate("dashboard_data")
        return {"status": "ok"}

    return router
