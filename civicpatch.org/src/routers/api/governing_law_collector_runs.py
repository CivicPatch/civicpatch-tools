"""Starting governing_law_collector runs, and what its state workflow asks. Its own router, ahead
of the scrape's, so these literal paths never meet `/pipeline_runs/{pipeline_run_id}/...`."""

from typing import Optional

import lib.temporal.client as temporal_service
import services.governing_law_collector_runs as collector_runs_service
import services.spend_budget as spend_budget_service
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import require_route_access
from pydantic import BaseModel
from routers.api.pipeline_runs import DISPATCH_MODE
from schemas.common import Identity, RouteCategory, UserRole
from shared.utils.statuses import PipelineRunKind

_ADMIN = require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
_SERVICE = require_route_access(RouteCategory.SERVICE)


class StartCollectionRequest(BaseModel):
    jurisdiction_ocdid: str


class CollectStateRequest(BaseModel):
    state: str
    # None is every jurisdiction due.
    num_jurisdictions: Optional[int] = None
    created_by_user_id: Optional[str] = None


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("", include_in_schema=False)
    async def start_collection_endpoint(body: StartCollectionRequest, user: Identity = Depends(_ADMIN)):
        try:
            claimed = await collector_runs_service.start_collection(body.jurisdiction_ocdid, user.user_id, DISPATCH_MODE)
        except collector_runs_service.UnknownJurisdiction:
            raise HTTPException(status_code=404, detail=f"No such jurisdiction: {body.jurisdiction_ocdid}")
        except collector_runs_service.AlreadyCollecting:
            raise HTTPException(status_code=409, detail="A collection for this jurisdiction is already running")
        return {"data": claimed.model_dump()}

    @router.post("/batch", include_in_schema=False)
    async def collect_state_endpoint(body: CollectStateRequest, user: Identity = Depends(_ADMIN)):
        workflow_id = await temporal_service.start_governing_law_collector_state_workflow(
            body.state, body.num_jurisdictions, user.user_id, DISPATCH_MODE
        )
        return {"data": {"workflow_id": workflow_id, "state": body.state}}

    @router.post("/claim", include_in_schema=False)
    async def claim_endpoint(body: CollectStateRequest, _: Identity = Depends(_SERVICE)):
        claimed = await collector_runs_service.claim_jurisdictions_for_governing_law_collector(
            body.state, body.num_jurisdictions, body.created_by_user_id
        )
        return {"data": {"jurisdictions": [run.model_dump() for run in claimed]}}

    @router.get("/budget_cap", include_in_schema=False)
    async def budget_cap_endpoint(_: Identity = Depends(_SERVICE)):
        cap = await spend_budget_service.cap_reached_for_collector(PipelineRunKind.GOVERNING_LAW_COLLECTOR)
        return {"data": {"cap": cap.value if cap else None}}

    return router
