import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleOverlapPolicy, SchedulePolicy, ScheduleSpec
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker

from routers.temporal.activities import sync_pr_state_activity, od_sync_activity, expire_stale_pipeline_runs_activity
from lib.temporal.workflows import PRSyncWorkflow, OdSyncWorkflow, PipelineRunCleanupWorkflow, ScheduleId, WorkflowInstanceId, TASK_QUEUE
from database.database import get_pool, close_pool

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")


async def _schedule_exists(client: Client, schedule_id: str) -> bool:
    try:
        await client.get_schedule_handle(schedule_id).describe()
        return True
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            return False
        raise


async def _register_schedules(client: Client) -> None:
    if not await _schedule_exists(client, ScheduleId.PR_SYNC):
        await client.create_schedule(
            ScheduleId.PR_SYNC,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    PRSyncWorkflow.run,
                    id=WorkflowInstanceId.PR_SYNC,
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(cron_expressions=["0 * * * *"]),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
            ),
        )

    if not await _schedule_exists(client, ScheduleId.OD_SYNC):
        handle = await client.create_schedule(
            ScheduleId.OD_SYNC,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    OdSyncWorkflow.run,
                    id=WorkflowInstanceId.OD_SYNC,
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(cron_expressions=["0 0 * * *"]),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
            ),
        )
        await handle.trigger()

    if not await _schedule_exists(client, ScheduleId.PIPELINE_RUN_CLEANUP):
        await client.create_schedule(
            ScheduleId.PIPELINE_RUN_CLEANUP,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    PipelineRunCleanupWorkflow.run,
                    id=WorkflowInstanceId.PIPELINE_RUN_CLEANUP,
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(cron_expressions=["*/15 * * * *"]),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
            ),
        )


async def main() -> None:
    await get_pool()
    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    await _register_schedules(client)
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[PRSyncWorkflow, OdSyncWorkflow, PipelineRunCleanupWorkflow],
        activities=[sync_pr_state_activity, od_sync_activity, expire_stale_pipeline_runs_activity],
    ):
        print(f"Worker started on task queue: {TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
