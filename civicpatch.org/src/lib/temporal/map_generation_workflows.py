"""The map-generation workflow: build one state's pmtiles, then refresh the national
coverage-picker overview. Runs on its own queue — see workers/maps.py.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from routers.temporal.map_generation_activities import (
        build_and_upload_national_overview,
        build_and_upload_state_pmtiles,
    )


@workflow.defn
class GenerateMapsWorkflow:
    """A state's pmtiles, then the national overview — chained so the coverage picker
    (`browse-map.ts`'s always-loaded `states.pmtiles`) can never silently omit a newly
    (re)generated state. See the map pipeline migration plan, decision 5.

    Idempotent and re-runnable: unlike a scrape, there's no run-status row to reconcile
    on failure — a failed attempt just needs re-triggering.
    """

    @workflow.run
    async def run(self, state: str) -> str:
        url = await workflow.execute_activity(
            build_and_upload_state_pmtiles,
            args=[state],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        await workflow.execute_activity(
            build_and_upload_national_overview,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        return url
