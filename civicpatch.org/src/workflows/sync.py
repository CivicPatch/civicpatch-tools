from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities.sync_activities import sync_pr_state_activity, od_sync_activity

TASK_QUEUE = "civicpatch-org-sync"


@workflow.defn
class PRSyncWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            sync_pr_state_activity,
            start_to_close_timeout=timedelta(minutes=30),
        )


@workflow.defn
class OdSyncWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            od_sync_activity,
            start_to_close_timeout=timedelta(minutes=60),
        )
