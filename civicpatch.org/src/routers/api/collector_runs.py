"""Starting a collector's runs, and what its state workflow asks. The kind is bound when the
router is mounted, at `/pipeline_runs/<kind>` ahead of the scrape's router, so these literal
paths never meet `/pipeline_runs/{pipeline_run_id}/...`."""

import lib.temporal.client as temporal_service
import services.collector_runs as collector_runs_service
import services.spend_budget as spend_budget_service
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import require_route_access
from routers.api.pipeline_runs import DISPATCH_MODE
from schemas.common import Identity, RouteCategory, UserRole
from schemas.pipeline_runs import BatchPipelineRunRequest, StartCollectionRequest
from shared.utils.statuses import PipelineRunKind

_ADMIN = require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
_SERVICE = require_route_access(RouteCategory.SERVICE)


def get_router(kind: PipelineRunKind) -> APIRouter:
    router = APIRouter()

    @router.post("", include_in_schema=False)
    async def start_collection_endpoint(body: StartCollectionRequest, user: Identity = Depends(_ADMIN)):
        try:
            claimed = await collector_runs_service.start_collection(kind, body.jurisdiction_ocdid, user.user_id, DISPATCH_MODE)
        except collector_runs_service.UnknownJurisdiction:
            raise HTTPException(status_code=404, detail=f"No such jurisdiction: {body.jurisdiction_ocdid}")
        except collector_runs_service.AlreadyCollecting:
            raise HTTPException(status_code=409, detail="A collection for this jurisdiction is already running")
        return {"data": claimed.model_dump()}

    @router.post("/batch", include_in_schema=False)
    async def collect_state_endpoint(body: BatchPipelineRunRequest, user: Identity = Depends(_ADMIN)):
        workflow_id = await temporal_service.start_collector_state_workflow(
            kind, body.state, body.num_jurisdictions, user.user_id, DISPATCH_MODE
        )
        return {"data": {"workflow_id": workflow_id, "state": body.state}}

    @router.post("/claim", include_in_schema=False)
    async def claim_endpoint(body: BatchPipelineRunRequest, _: Identity = Depends(_SERVICE)):
        claimed = await collector_runs_service.claim_jurisdictions(kind, body.state, body.num_jurisdictions, body.created_by_user_id)
        return {"data": {"jurisdictions": [run.model_dump() for run in claimed]}}

    @router.get("/budget_cap", include_in_schema=False)
    async def budget_cap_endpoint(_: Identity = Depends(_SERVICE)):
        cap = await spend_budget_service.cap_reached_for_collector(kind)
        return {"data": {"cap": cap.value if cap else None}}

    return router
