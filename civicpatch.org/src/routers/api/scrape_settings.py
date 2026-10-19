"""Cadence and budget, per state and for everything together.

**Two gates, deliberately.** `can_write_config` (MAINTAINERS) sets how often a state is scraped;
`can_write_global_config` (ADMINS) sets what it may spend. That separates *how much money
exists* from *how it gets used*, which is how budgets actually work — and both permissions
already existed, so this adds none.

Admin throughout, read and write. Cadence and budget are one decision — how often a state is
scraped is what it costs — so splitting them across two roles made a maintainer able to set the
spending without the number it is measured against.
"""

import logging

from database import collector_settings as collector_settings_db
from database import state_settings as db
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.collector_settings import SetCollectorCapsRequest
from schemas.scrape_settings import SetCadenceRequest, SetCapsRequest, SetGlobalCapRequest
from lib.temporal.client import get_client
from lib.temporal.schedules import reconcile_state_schedule
import services.collector_settings as collector_settings_service
from services.scrape_settings import get_global_panel, get_state_panel
from shared.utils.statuses import COLLECTOR_RUN_KINDS, PipelineRunKind

logger = logging.getLogger(__name__)

_ADMIN = require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)


def _require_collector(kind: PipelineRunKind) -> None:
    if kind not in COLLECTOR_RUN_KINDS:
        raise HTTPException(status_code=404, detail=f"{kind} is the scrape: its caps are per state")


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("/global")
    async def get_global_settings_endpoint(_: Identity = Depends(_ADMIN)):
        return {"data": (await get_global_panel()).model_dump(mode="json")}

    @router.put("/global")
    async def put_global_cap_endpoint(
        body: SetGlobalCapRequest, user: Identity = Depends(_ADMIN)
    ):
        await db.set_global_cap(body.monthly_cap_usd, user.user_id)
        return {"data": (await get_global_panel()).model_dump(mode="json")}

    # The charter collectors' bounds, apart from the scrape's: one row per kind, not per state.
    @router.get("/collectors")
    async def get_collector_panels_endpoint(_: Identity = Depends(_ADMIN)):
        return {"data": [panel.model_dump(mode="json") for panel in await collector_settings_service.get_collector_panels()]}

    @router.get("/collectors/{kind}")
    async def get_collector_settings_endpoint(kind: PipelineRunKind, _: Identity = Depends(_ADMIN)):
        _require_collector(kind)
        return {"data": (await collector_settings_db.get_collector_settings(kind)).model_dump(mode="json")}

    @router.put("/collectors/{kind}")
    async def put_collector_settings_endpoint(
        kind: PipelineRunKind, body: SetCollectorCapsRequest, user: Identity = Depends(_ADMIN)
    ):
        _require_collector(kind)
        await collector_settings_db.set_collector_caps(kind, body.pipeline_run_cap_usd, body.monthly_cap_usd, user.user_id)
        return {"data": (await collector_settings_db.get_collector_settings(kind)).model_dump(mode="json")}

    @router.get("/{state}")
    async def get_state_settings_endpoint(state: str, _: Identity = Depends(_ADMIN)):
        return {"data": (await get_state_panel(state)).model_dump(mode="json")}

    @router.put("/{state}/cadence")
    async def put_cadence_endpoint(
        state: str, body: SetCadenceRequest, user: Identity = Depends(_ADMIN)
    ):
        await db.set_cadence(state, body.cadence_days, body.cadence_anchor, user.user_id)
        # The table is the source of truth and the schedule is a projection of it, so the
        # projection is converged here rather than left to drift until the next worker start.
        # Failing to converge must not fail the write: the worker's own pass will catch up.
        try:
            await reconcile_state_schedule(await get_client(), state)
        except Exception:
            logger.exception(
                "Saved cadence for %s but could not converge its schedule", state
            )
        return {"data": (await db.get_state_settings(state)).model_dump(mode="json")}

    @router.put("/{state}/caps")
    async def put_caps_endpoint(
        state: str, body: SetCapsRequest, user: Identity = Depends(_ADMIN)
    ):
        await db.set_caps(
            state, body.pipeline_run_cap_usd, body.monthly_cap_usd, user.user_id
        )
        return {"data": (await db.get_state_settings(state)).model_dump(mode="json")}

    return router
