from fastapi import APIRouter, BackgroundTasks, Depends

import services.github.data_sync_service
import services.github.pull_request_sync_service
from schemas.common import Identity, Role, RouteCategory
from schemas.requests import OdSyncRequestSchema
from utils.auth_utils import require_route_access

def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/od_sync", include_in_schema=False)
    async def od_sync_endpoint(
        request: OdSyncRequestSchema,
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS])),
    ):
        background_tasks.add_task(services.github.data_sync_service.sync, request)

        return {"status": "running"}

    @router.post("/pr_sync", include_in_schema=False)
    async def pr_sync_endpoint(
        background_tasks: BackgroundTasks,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS])),
    ):
        background_tasks.add_task(services.github.pull_request_sync_service.sync_open_pr_state)
        return {"status": "running"}

    return router
