"""What the state settings block shows.

Assembled here rather than in the router: it is five reads and one piece of arithmetic, which
is orchestration, and routers in this codebase do none.
"""

from datetime import datetime, timezone

from core.scrape_schedule import next_run_at
from database.issues import count_cost_cap_hits_this_month
from database.pipeline_run_spend import get_month_to_date_spend
from database.state_settings import (
    get_global_settings,
    get_state_settings,
    sum_state_monthly_caps,
)
from schemas.scrape_settings import GlobalScrapePanel, StateScrapePanel
from services.jurisdiction_scrape_candidate import get_scrape_candidates
from services.spend_budget import cap_reached_for_state


async def get_state_panel(state: str) -> StateScrapePanel:
    settings = await get_state_settings(state)
    fleet = await get_global_settings()
    state_spent, global_spent = await get_month_to_date_spend(state)
    cap_reached = await cap_reached_for_state(state)
    hits = await count_cost_cap_hits_this_month(state)
    candidates = await get_scrape_candidates(state)

    return StateScrapePanel(
        state=state,
        cadence_days=settings.cadence_days,
        cadence_anchor=settings.cadence_anchor,
        next_run_at=next_run_at(
            settings.cadence_days, settings.cadence_anchor, datetime.now(timezone.utc)
        ),
        pipeline_run_cap_usd=settings.pipeline_run_cap_usd,
        monthly_cap_usd=settings.monthly_cap_usd,
        global_monthly_cap_usd=fleet.monthly_cap_usd,
        spent_this_month_usd=state_spent,
        global_spent_this_month_usd=global_spent,
        cap_reached=cap_reached.value if cap_reached else None,
        cost_cap_hits_this_month=hits,
        candidates_due=len(candidates),
    )


async def get_global_panel() -> GlobalScrapePanel:
    fleet = await get_global_settings()
    # Any state gives the same all-states figure; the per-state half is discarded.
    _state_spent, global_spent = await get_month_to_date_spend("")
    return GlobalScrapePanel(
        monthly_cap_usd=fleet.monthly_cap_usd,
        spent_this_month_usd=global_spent,
        state_monthly_caps_usd=await sum_state_monthly_caps(),
    )
