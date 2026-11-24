"""What one pipeline's settings block in one state shows, and the global block. Orchestration only."""

from datetime import datetime, timezone

import environment
from core.scrape_schedule import next_run_at
from database.issue_listings import count_cost_cap_hits_this_month
from database.pipeline_run_spend import (
    get_fleet_month_to_date_cost_per_run,
    get_fleet_month_to_date_seconds_per_run,
    get_month_to_date_cost_per_run,
    get_month_to_date_spend,
)
from database.pipeline_settings import get_pipeline_settings, sum_monthly_caps
from database.global_settings import get_global_settings
from schemas.pipeline_settings import GlobalPanel, PipelinePanel
from services.collector_runs import CANDIDATES
from services.jurisdiction_scrape_candidate import get_scrape_candidates
from services.spend_budget import cap_reached_for
from shared.utils.statuses import PipelineRunKind


async def _candidates_due(state: str, kind: PipelineRunKind) -> int:
    if kind == PipelineRunKind.PEOPLE_COLLECTOR:
        return len(await get_scrape_candidates(state))
    return len(await CANDIDATES[kind](state, None))


async def get_pipeline_panel(state: str, kind: PipelineRunKind) -> PipelinePanel:
    settings = await get_pipeline_settings(state, kind)
    fleet = await get_global_settings()
    spent, global_spent = await get_month_to_date_spend(state, kind)
    cap = await cap_reached_for(state, kind)
    return PipelinePanel(
        state=state,
        kind=kind,
        cadence_days=settings.cadence_days,
        cadence_anchor=settings.cadence_anchor,
        next_run_at=next_run_at(settings.cadence_days, settings.cadence_anchor, datetime.now(timezone.utc)),
        pipeline_run_cap_usd=settings.pipeline_run_cap_usd,
        monthly_cap_usd=settings.monthly_cap_usd,
        global_monthly_cap_usd=fleet.monthly_cap_usd,
        spent_this_month_usd=spent,
        global_spent_this_month_usd=global_spent,
        cap_reached=cap.value if cap else None,
        cost_per_run_this_month_usd=await get_month_to_date_cost_per_run(state, kind),
        cost_cap_hits_this_month=await count_cost_cap_hits_this_month(state, kind),
        candidates_due=await _candidates_due(state, kind),
    )


async def get_global_panel() -> GlobalPanel:
    fleet = await get_global_settings()
    # Any state and pipeline give the same all-states figure; the per-state half is discarded.
    _spent, global_spent = await get_month_to_date_spend("", PipelineRunKind.PEOPLE_COLLECTOR)
    return GlobalPanel(
        monthly_cap_usd=fleet.monthly_cap_usd,
        spent_this_month_usd=global_spent,
        monthly_caps_usd=await sum_monthly_caps(),
        cost_per_run_this_month_usd=await get_fleet_month_to_date_cost_per_run(),
        seconds_per_run_this_month=await get_fleet_month_to_date_seconds_per_run(),
        pipeline_run_concurrency=int(environment.get_env_vars()["PIPELINE_RUN_CONCURRENCY"]),
    )
