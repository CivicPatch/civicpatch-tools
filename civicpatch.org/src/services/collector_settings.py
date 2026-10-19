"""What the Pipelines page's Collectors section shows: one panel per charter collector kind."""

from database.collector_settings import get_collector_settings
from database.issue_listings import count_collector_cost_cap_hits_this_month
from database.pipeline_run_spend import get_collector_month_to_date_runs, get_collector_month_to_date_spend
from schemas.collector_settings import CollectorPanel
from shared.utils.statuses import COLLECTOR_RUN_KINDS, PipelineRunKind


async def get_collector_panel(kind: PipelineRunKind) -> CollectorPanel:
    runs, cost_per_run = await get_collector_month_to_date_runs(kind)
    return CollectorPanel(
        settings=await get_collector_settings(kind),
        spent_this_month_usd=await get_collector_month_to_date_spend(kind),
        cost_per_run_this_month_usd=cost_per_run,
        runs_this_month=runs,
        cost_cap_hits_this_month=await count_collector_cost_cap_hits_this_month(kind),
    )


async def get_collector_panels() -> list[CollectorPanel]:
    return [await get_collector_panel(kind) for kind in COLLECTOR_RUN_KINDS]
