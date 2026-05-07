from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator

from lib.auth import require_route_access
from schemas.common import Identity, Role, RouteCategory
from shared.utils.config_utils import get_states
import lib.temporal.map_client as map_client


def _valid_state_codes() -> set[str]:
    return {s["code"] for s in get_states()}


class SyncJurisdictionMapRequest(BaseModel):
    state: Optional[str] = None

    @model_validator(mode="after")
    def validate_state(self) -> "SyncJurisdictionMapRequest":
        if self.state is not None and self.state not in _valid_state_codes():
            raise ValueError(f"state must be one of: {sorted(_valid_state_codes())}")
        return self


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/sync", include_in_schema=False)
    async def sync_jurisdiction_map(
        request: SyncJurisdictionMapRequest = SyncJurisdictionMapRequest(),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.ADMINS])),
    ):
        try:
            workflow_id = await map_client.start_sync_jurisdiction_map_workflow(request.state)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"workflow_id": workflow_id, "state": request.state}

    return router
