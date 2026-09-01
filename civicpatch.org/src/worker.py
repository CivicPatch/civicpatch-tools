import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)

from database.database import get_pool
from lib.temporal.workflows import (
    TASK_QUEUE,
    OdSyncTargetedWorkflow,
    OdSyncWorkflow,
    OpenDataBatchCommitWorkflow,
    OpenDataCommitWorkflow,
    PipelineRunCleanupWorkflow,
    ReviewSessionCleanupWorkflow,
    ScheduleId,
    WorkflowInstanceId,
)
from routers.temporal.activities import (
    cleanup_stale_review_entries_activity,
    commit_open_data_activity,
    commit_open_data_batch_activity,
    expire_stale_pipeline_runs_activity,
    od_sync_activity,
    od_sync_targeted_activity,
    supersede_stacked_requests_activity,
)
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleUpdate,
)
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")


def _is_duplicate_schedule_error(e: RPCError) -> bool:
    return e.status == RPCStatusCode.ALREADY_EXISTS or "duplicate key" in str(e)


async def _ensure_schedule(
    client: Client, schedule_id: str, schedule: Schedule
) -> bool:
    """Idempotent create-or-update for one schedule: create it if absent, otherwise update its
    spec in place, so calling this repeatedly converges on `schedule` rather than erroring.

    Callers below pass schedules declared in this file, so for those the declaration is what
    propagates on the next worker start. That is a property of those call sites, not of this
    function — a caller reading desired state from anywhere else works the same way.

    Returns True only when newly created, so the caller can trigger an immediate first run."""
    try:
        await client.create_schedule(schedule_id, schedule)
        return True
    except ScheduleAlreadyRunningError:
        pass
    except RPCError as e:
        if not _is_duplicate_schedule_error(e):
            raise
    await client.get_schedule_handle(schedule_id).update(
        lambda _input: ScheduleUpdate(schedule=schedule)
    )
    return False


async def _register_schedules(client: Client) -> None:
    created = await _ensure_schedule(
        client,
        ScheduleId.OD_SYNC,
        Schedule(
            action=ScheduleActionStartWorkflow(
                OdSyncWorkflow.run,
                id=WorkflowInstanceId.OD_SYNC,
                task_queue=TASK_QUEUE,
            ),
            spec=ScheduleSpec(cron_expressions=["0 * * * *"]),
            policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        ),
    )
    if created:
        await client.get_schedule_handle(ScheduleId.OD_SYNC).trigger()

    await _ensure_schedule(
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

    await _ensure_schedule(
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
                    OdSyncWorkflow,
            OdSyncTargetedWorkflow,
            OpenDataCommitWorkflow,
            OpenDataBatchCommitWorkflow,
            PipelineRunCleanupWorkflow,
                    ReviewSessionCleanupWorkflow,
        ],
        activities=[
                    od_sync_activity,
            od_sync_targeted_activity,
            expire_stale_pipeline_runs_activity,
            cleanup_stale_review_entries_activity,
                    commit_open_data_activity,
            commit_open_data_batch_activity,
            supersede_stacked_requests_activity,
        ],
    ):
        print(f"Worker started on task queue: {TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
