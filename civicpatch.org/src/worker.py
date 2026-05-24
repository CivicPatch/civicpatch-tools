import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleAlreadyRunningError, ScheduleOverlapPolicy, SchedulePolicy, ScheduleSpec
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker

from routers.temporal.activities import (
    sync_pr_state_activity,
    od_sync_activity,
    expire_stale_pipeline_runs_activity,
    cleanup_stale_review_entries_activity,
    merge_pr_activity,
)
from lib.temporal.workflows import (
    PRSyncWorkflow,
    OdSyncWorkflow,
    PipelineRunCleanupWorkflow,
    RepoMergeQueueWorkflow,
    ReviewSessionCleanupWorkflow,
    ScheduleId,
    WorkflowInstanceId,
    TASK_QUEUE,
)
from database.database import get_pool, close_pool

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")


def _is_duplicate_schedule_error(e: RPCError) -> bool:
    return e.status == RPCStatusCode.ALREADY_EXISTS or "duplicate key" in str(e)


async def _create_schedule(client: Client, schedule_id: str, schedule: Schedule) -> bool:
    """Returns True if the schedule was newly created, False if it already existed."""
    try:
        await client.create_schedule(schedule_id, schedule)
        return True
    except ScheduleAlreadyRunningError:
        return False
    except RPCError as e:
        if _is_duplicate_schedule_error(e):
            return False
        raise


async def _register_schedules(client: Client) -> None:
    await _create_schedule(
        client,
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

    created = await _create_schedule(
        client,
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
    if created:
        await client.get_schedule_handle(ScheduleId.OD_SYNC).trigger()

    await _create_schedule(
        client,
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

    await _create_schedule(
        client,
        ScheduleId.REVIEW_SESSION_CLEANUP,
        Schedule(
            action=ScheduleActionStartWorkflow(
                ReviewSessionCleanupWorkflow.run,
                id=WorkflowInstanceId.REVIEW_SESSION_CLEANUP,
                task_queue=TASK_QUEUE,
            ),
            spec=ScheduleSpec(cron_expressions=["*/10 * * * *"]),
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
        workflows=[
            PRSyncWorkflow,
            OdSyncWorkflow,
            PipelineRunCleanupWorkflow,
            RepoMergeQueueWorkflow,
            ReviewSessionCleanupWorkflow,
        ],
        activities=[
            sync_pr_state_activity,
            od_sync_activity,
            expire_stale_pipeline_runs_activity,
            cleanup_stale_review_entries_activity,
            merge_pr_activity,
        ],
    ):
        print(f"Worker started on task queue: {TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
