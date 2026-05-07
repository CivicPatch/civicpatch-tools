from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, model_validator

import lib.cache as cache_service
import core.open_data_sync as data_sync
import core.pull_request_sync as pr_sync
import lib.temporal.map_client as map_client
from schemas.common import Identity, Role, RouteCategory
from schemas.open_data import OdSyncRequestSchema
from lib.auth import require_route_access
from shared.utils.config_utils import get_states


def _valid_state_codes() -> set[str]:
    return {s["code"] for s in get_states()}


class MapSyncRequest(BaseModel):
    state: Optional[str] = None

    @model_validator(mode="after")
    def validate_state(self) -> "MapSyncRequest":
        if self.state is not None and self.state not in _valid_state_codes():
            raise ValueError(f"state must be one of: {sorted(_valid_state_codes())}")
        return self

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

    @router.post("/map_sync", include_in_schema=False)
    async def map_sync_endpoint(
        request: MapSyncRequest = MapSyncRequest(),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS])),
    ):
        try:
            workflow_id = await map_client.start_sync_jurisdiction_map_workflow(request.state)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"workflow_id": workflow_id, "state": request.state}

    return router
