"""Cadence and caps for each pipeline in each state, and the global cap. Admin throughout: how often
a pipeline runs is what it costs, so one role sets both."""

import logging

from database import pipeline_settings as db
from database.global_settings import set_global_cap
from fastapi import APIRouter, Depends
from lib.auth import require_route_access
from lib.temporal.client import get_client
from lib.temporal.schedules import reconcile_state_schedule
from schemas.common import Identity, RouteCategory, UserRole
from schemas.pipeline_settings import SetCadenceRequest, SetCapsRequest, SetGlobalCapRequest
from services.pipeline_settings import get_global_panel, get_pipeline_panel
from shared.utils.statuses import PipelineRunKind

logger = logging.getLogger(__name__)

_ADMIN = require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/global")
    async def get_global_settings_endpoint(_: Identity = Depends(_ADMIN)):
        return {"data": (await get_global_panel()).model_dump(mode="json")}

    @router.put("/global")
    async def put_global_cap_endpoint(body: SetGlobalCapRequest, user: Identity = Depends(_ADMIN)):
        await set_global_cap(body.monthly_cap_usd, user.user_id)
        return {"data": (await get_global_panel()).model_dump(mode="json")}

    @router.get("/{state}/{kind}")
    async def get_pipeline_settings_endpoint(state: str, kind: PipelineRunKind, _: Identity = Depends(_ADMIN)):
        return {"data": (await get_pipeline_panel(state, kind)).model_dump(mode="json")}

    @router.put("/{state}/{kind}/cadence")
    async def put_cadence_endpoint(
        state: str, kind: PipelineRunKind, body: SetCadenceRequest, user: Identity = Depends(_ADMIN)
    ):
        await db.set_cadence(state, kind, body.cadence_days, body.cadence_anchor, user.user_id)
        # The table is the source of truth and the schedule a projection of it. Failing to converge must
        # not fail the write: the worker's own pass catches up.
        try:
            await reconcile_state_schedule(await get_client(), state, kind)
        except Exception:
            logger.exception("Saved the cadence for %s %s but could not converge its schedule", state, kind)
        return {"data": (await get_pipeline_panel(state, kind)).model_dump(mode="json")}

    @router.put("/{state}/{kind}/caps")
    async def put_caps_endpoint(
        state: str, kind: PipelineRunKind, body: SetCapsRequest, user: Identity = Depends(_ADMIN)
    ):
        await db.set_caps(state, kind, body.pipeline_run_cap_usd, body.monthly_cap_usd, user.user_id)
        return {"data": (await get_pipeline_panel(state, kind)).model_dump(mode="json")}

    return router
