from datetime import timedelta
from typing import Optional

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from routers.temporal.map_activities import sync_jurisdiction_map_activity
    from shared.utils.config_utils import get_states

TASK_QUEUE = "open-data-map-sync"


@workflow.defn
class SyncJurisdictionMapWorkflow:
    @workflow.run
    async def run(self, state: Optional[str] = None) -> list[str]:
        states = [state] if state else [s["code"] for s in get_states()]
        results = []
        for s in states:
            url = await workflow.execute_activity(
                sync_jurisdiction_map_activity,
                s,
                start_to_close_timeout=timedelta(minutes=30),
            )
            results.append(url)
        return results
