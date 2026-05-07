from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from routers.temporal.map_activities import sync_jurisdiction_map_activity
    from lib.temporal.workflows import TASK_QUEUE


@workflow.defn
class SyncJurisdictionMapWorkflow:
    @workflow.run
    async def run(self, states: list[str]) -> list[str]:
        results = []
        for s in states:
            url = await workflow.execute_activity(
                sync_jurisdiction_map_activity,
                s,
                start_to_close_timeout=timedelta(minutes=30),
            )
            results.append(url)
        return results
