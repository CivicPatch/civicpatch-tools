import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database.database import get_pool
from lib.temporal.workflows import (
    TASK_QUEUE,
    OdSyncTargetedWorkflow,
    OdSyncWorkflow,
    JurisdictionsSheetSyncWorkflow,
    OpenDataBatchCommitWorkflow,
    SweepChangesWorkflow,
    SweepEverythingWorkflow,
    RosterSheetSyncWorkflow,
    PipelineRunCleanupWorkflow,
    ReviewSessionCleanupWorkflow,
    ScheduleId,
    WorkflowInstanceId,
)
from routers.temporal.activities import (
    cleanup_stale_review_entries_activity,
    commit_open_data_batch_activity,
    expire_stale_pipeline_runs_activity,
    od_sync_activity,
    od_sync_targeted_activity,
    supersede_stacked_requests_activity,
    backstop_open_data_activity,
    list_states_activity,
    sync_roster_parquet_activity,
    sweep_open_data_activity,
    sweep_roster_sheets_activity,
    sync_jurisdictions_sheet_activity,
    sync_roster_sheet_activity,
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

WORKFLOWS = [
    OdSyncWorkflow,
    OdSyncTargetedWorkflow,
    OpenDataBatchCommitWorkflow,
    PipelineRunCleanupWorkflow,
    ReviewSessionCleanupWorkflow,
    RosterSheetSyncWorkflow,
    JurisdictionsSheetSyncWorkflow,
    SweepChangesWorkflow,
    SweepEverythingWorkflow,
]


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


async def _retire_undeclared_schedules(client: Client, declared: set[str]) -> None:
    """Delete schedules this worker no longer declares.

    `_ensure_schedule` converges what is declared; nothing removed what stopped being. A
    Temporal schedule is server state that outlives the code, so deleting a workflow class left
    its schedule firing forever — the worker then rejected every firing with
    `NotFoundError: Workflow class ... is not registered`, and looked dead while doing it.
    That is exactly what `pr-sync` did.

    This worker is the only thing that creates schedules in this namespace, so anything else
    here is a leftover. Logged rather than silent: deleting server state on startup should say
    what it deleted.
    """
    async for existing in await client.list_schedules():
        if existing.id in declared:
            continue
        logger.info("Retiring schedule no longer declared: %s", existing.id)
        await client.get_schedule_handle(existing.id).delete()


async def _terminate_undeclared_workflows(client: Client, declared: set[str]) -> None:
    """Terminate running executions whose workflow class this worker no longer registers.

    Retiring a schedule stops new firings but leaves executions it already started open, failing
    every workflow task with `NotFoundError: Workflow class ... is not registered`. `pr-sync` sat
    that way for a week across 1139 attempts.

    Terminate rather than cancel: cancellation is delivered to the workflow for its own code to
    act on, and that code is precisely what no longer exists. Scoped to this worker's task queue
    because the pipelines worker shares the namespace and registers a different set.
    """
    async for execution in client.list_workflows(
        f"ExecutionStatus='Running' AND TaskQueue='{TASK_QUEUE}'"
    ):
        if execution.workflow_type in declared:
            continue
        logger.info(
            "Terminating %s: workflow class %s is no longer registered",
            execution.id,
            execution.workflow_type,
        )
        await client.get_workflow_handle(
            execution.id, run_id=execution.run_id
        ).terminate(reason="workflow class no longer registered on this worker")


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

    await _ensure_schedule(
        client,
        ScheduleId.SWEEP_CHANGES,
        Schedule(
            action=ScheduleActionStartWorkflow(
                SweepChangesWorkflow.run,
                id=WorkflowInstanceId.SWEEP_CHANGES,
                task_queue=TASK_QUEUE,
            ),
            # Every five minutes, against a fifteen-minute lookback. This is both mirrors'
            # only route in during normal running, so the gap between a publish and the tab
            # is this plus the debounce.
            spec=ScheduleSpec(cron_expressions=["*/5 * * * *"]),
            policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        ),
    )


    await _ensure_schedule(
        client,
        ScheduleId.SWEEP_EVERYTHING,
        Schedule(
            action=ScheduleActionStartWorkflow(
                SweepEverythingWorkflow.run,
                id=WorkflowInstanceId.SWEEP_EVERYTHING,
                task_queue=TASK_QUEUE,
            ),
            # 09:00 UTC, which is the quiet end of a US night. Nothing depends on the hour;
            # what matters is that it is far from the 5-minute sweep's busy periods.
            spec=ScheduleSpec(cron_expressions=["0 9 * * *"]),
            policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        ),
    )

    # The five above are the whole set. Anything else on the server is from a version that
    # declared more than this one does — including a schedule this file renamed, which is why
    # `sync-sweep` disappears on the first boot after `SWEEP_CHANGES` replaced it.
    await _retire_undeclared_schedules(
        client,
        {
            ScheduleId.OD_SYNC,
            ScheduleId.PIPELINE_RUN_CLEANUP,
            ScheduleId.REVIEW_SESSION_CLEANUP,
            ScheduleId.SWEEP_CHANGES,
            ScheduleId.SWEEP_EVERYTHING,
        },
    )


ACTIVITIES = [
    od_sync_activity,
    od_sync_targeted_activity,
    expire_stale_pipeline_runs_activity,
    cleanup_stale_review_entries_activity,
    commit_open_data_batch_activity,
    supersede_stacked_requests_activity,
    sync_roster_sheet_activity,
    sync_jurisdictions_sheet_activity,
    sweep_open_data_activity,
    sweep_roster_sheets_activity,
    backstop_open_data_activity,
    list_states_activity,
    sync_roster_parquet_activity,
]


async def main() -> None:
    await get_pool()

    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    await _register_schedules(client)
    await _terminate_undeclared_workflows(
        client, {workflow.__name__ for workflow in WORKFLOWS}
    )
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
    ):
        print(f"Worker started on task queue: {TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
