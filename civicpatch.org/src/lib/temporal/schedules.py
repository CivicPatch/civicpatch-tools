"""The five schedules, declared in one place and owned by one worker.

**Why one owner.** `retire_undeclared_schedules` deletes any schedule on the server that is not
in the declared set — that is what stops a renamed or deleted workflow firing forever against a
worker that no longer registers it (`pr-sync` did exactly that for a week, 1139 failed
attempts). Schedules are namespace-wide, so if each of the four workers declared only its own,
every boot would delete the other three's. One worker declares all five; the others just poll.

**Why workflows are named by string here.** A schedule names a workflow and a task queue; it
does not need the class. Importing the classes would pull every activity module — and every
service behind them — into whichever worker owns registration, which is precisely the import
graph the split exists to avoid. `client.py` already starts two workflows this way.

The cost of the string form is that a rename is not typechecked. `_terminate_undeclared_workflows`
is the backstop: a schedule firing a workflow class nobody registers surfaces immediately as
terminated executions rather than silent failures.
"""

import logging

from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleAlreadyRunningError,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleUpdate,
)
from temporalio.service import RPCError, RPCStatusCode

from core.scrape_schedule import interval_offset, schedule_id as state_schedule_id
from database.state_settings import get_all_state_settings, get_state_settings
from lib.temporal.types import (
    CLEANUP_TASK_QUEUE,
    PIPELINE_RUNS_TASK_QUEUE,
    SINKS_TASK_QUEUE,
    SOURCE_TASK_QUEUE,
    ScheduleId,
    WorkflowInstanceId,
)

logger = logging.getLogger(__name__)

# schedule id -> (workflow type name, instance id, task queue, cron)
_SCHEDULES = {
    ScheduleId.SOURCE_OPEN_DATA_JURISDICTIONS: (
        "ReadOpenDataJurisdictionsWorkflow",
        WorkflowInstanceId.SOURCE_OPEN_DATA_JURISDICTIONS,
        SOURCE_TASK_QUEUE,
        "0 * * * *",
    ),
    ScheduleId.CLEANUP_PIPELINE_RUNS: (
        "CleanupPipelineRunsWorkflow",
        WorkflowInstanceId.CLEANUP_PIPELINE_RUNS,
        CLEANUP_TASK_QUEUE,
        "*/15 * * * *",
    ),
    ScheduleId.CLEANUP_REVIEW_SESSIONS: (
        "CleanupReviewSessionsWorkflow",
        WorkflowInstanceId.CLEANUP_REVIEW_SESSIONS,
        CLEANUP_TASK_QUEUE,
        "*/10 * * * *",
    ),
    # Every five minutes, against a fifteen-minute lookback. This is both mirrors' only route
    # in during normal running, so the gap between a publish and the tab is this plus the
    # debounce.
    ScheduleId.SINK_WRITE_RECENT_CHANGES: (
        "WriteRecentChangesWorkflow",
        WorkflowInstanceId.SINK_WRITE_RECENT_CHANGES,
        SINKS_TASK_QUEUE,
        "*/5 * * * *",
    ),
    # 09:00 UTC, the quiet end of a US night. Nothing depends on the hour; what matters is that
    # it is far from the 5-minute sweep's busy periods.
    ScheduleId.SINK_WRITE_EVERYTHING: (
        "WriteEverythingWorkflow",
        WorkflowInstanceId.SINK_WRITE_EVERYTHING,
        SINKS_TASK_QUEUE,
        "0 9 * * *",
    ),
}


def _is_duplicate_schedule_error(e: RPCError) -> bool:
    return e.status == RPCStatusCode.ALREADY_EXISTS or "duplicate key" in str(e)


async def _ensure_schedule(
    client: Client, schedule_id: str, schedule: Schedule
) -> bool:
    """Idempotent create-or-update for one schedule: create it if absent, otherwise update its
    spec in place, so calling this repeatedly converges on `schedule` rather than erroring.

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


async def _register_state_schedules(client: Client) -> set[str]:
    """One schedule per state that has a cadence, declared from `state_settings`.

    Returns the ids it declared, because they have to join the fixed five in the set passed to
    `_retire_undeclared_schedules` — omitting them would make every worker start delete every
    state schedule, which is the trap this plan flagged before it was built.

    **A state with a NULL cadence gets no schedule**, which is what `manual` means. Setting a
    cadence back to NULL therefore deletes its schedule, by the same omission — the retire pass
    is the delete path, so there is no second one to keep in step.

    `SKIP` on overlap: a state's pass can outlast its own interval — Michigan is 1,293
    jurisdictions — and stacking a second pass on top of a running one would claim candidates
    the first is still working through.
    """
    declared: set[str] = set()
    for state, settings in (await get_all_state_settings()).items():
        if settings.cadence_days is None:
            continue
        every = timedelta(days=settings.cadence_days)
        schedule_id = state_schedule_id(state)
        declared.add(schedule_id)
        await _ensure_schedule(
            client,
            schedule_id,
            Schedule(
                # `args` is the state and nothing else: a schedule can only pass fixed
                # arguments, and StateScrapeWorkflow.run defaults the rest deliberately so a
                # scheduled scrape and a hand-started one take the same path.
                action=ScheduleActionStartWorkflow(
                    "StateScrapeWorkflow",
                    args=[state],
                    id=f"state-scrape-{state}",
                    task_queue=PIPELINE_RUNS_TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    intervals=[
                        ScheduleIntervalSpec(
                            every=every,
                            offset=interval_offset(settings.cadence_anchor, every),
                        )
                    ]
                ),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
            ),
        )
    return declared


async def register_schedules(client: Client) -> None:
    """Converge every declared schedule, then delete anything else in the namespace."""
    for schedule_id, (workflow_name, instance_id, task_queue, cron) in _SCHEDULES.items():
        created = await _ensure_schedule(
            client,
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow_name,
                    id=instance_id,
                    task_queue=task_queue,
                ),
                spec=ScheduleSpec(cron_expressions=[cron]),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
            ),
        )
        # Only the inbound read earns an immediate first run; the others fire soon enough on their own.
        if created and schedule_id == ScheduleId.SOURCE_OPEN_DATA_JURISDICTIONS:
            await client.get_schedule_handle(schedule_id).trigger()

    # The union, not the literal: state schedules are declared from the table, and leaving
    # them out of this set would delete all of them on the next worker start.
    state_ids = await _register_state_schedules(client)
    await _retire_undeclared_schedules(client, set(_SCHEDULES) | state_ids)


async def _retire_undeclared_schedules(client: Client, declared: set[str]) -> None:
    """Delete schedules no longer declared.

    `_ensure_schedule` converges what is declared; nothing removed what stopped being. A
    Temporal schedule is server state that outlives the code, so deleting a workflow class left
    its schedule firing forever — the worker then rejected every firing with
    `NotFoundError: Workflow class ... is not registered`, and looked dead while doing it.
    That is exactly what `pr-sync` did.

    Logged rather than silent: deleting server state on startup should say what it deleted.
    """
    async for existing in await client.list_schedules():
        if existing.id in declared:
            continue
        logger.info("Retiring schedule no longer declared: %s", existing.id)
        await client.get_schedule_handle(existing.id).delete()


async def terminate_undeclared_workflows(
    client: Client, task_queue: str, declared: set[str]
) -> None:
    """Terminate running executions on `task_queue` whose class this worker does not register.

    Retiring a schedule stops new firings but leaves executions it already started open, failing
    every workflow task with `NotFoundError: Workflow class ... is not registered`. `pr-sync` sat
    that way for a week across 1139 attempts.

    Terminate rather than cancel: cancellation is delivered to the workflow for its own code to
    act on, and that code is precisely what no longer exists. Scoped to one task queue so each
    worker only ever terminates its own.
    """
    async for execution in client.list_workflows(
        f"ExecutionStatus='Running' AND TaskQueue='{task_queue}'"
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


async def reconcile_state_schedule(client: Client, state: str) -> None:
    """Converge one state's schedule, right after its cadence was written.

    Targeted on purpose: `register_schedules` ends in a retire pass over the whole namespace,
    and running that from the API would let a request delete schedules it knows nothing about.
    This touches one id and nothing else.

    Deleting when the cadence is NULL is explicit here, unlike at worker start where omission
    from the declared set does it. Two paths, because there is no retire pass to lean on — and
    a `manual` state that kept firing would be the worst failure this feature has.
    """
    settings = await get_state_settings(state)
    schedule_id = state_schedule_id(state)

    if settings.cadence_days is None:
        try:
            await client.get_schedule_handle(schedule_id).delete()
            logger.info("Deleted schedule for %s: cadence is now manual", state)
        except RPCError as e:
            if e.status != RPCStatusCode.NOT_FOUND:
                raise
        return

    every = timedelta(days=settings.cadence_days)
    await _ensure_schedule(
        client,
        schedule_id,
        Schedule(
            action=ScheduleActionStartWorkflow(
                "StateScrapeWorkflow",
                args=[state],
                id=f"state-scrape-{state}",
                task_queue=PIPELINE_RUNS_TASK_QUEUE,
            ),
            spec=ScheduleSpec(
                intervals=[
                    ScheduleIntervalSpec(
                        every=every,
                        offset=interval_offset(settings.cadence_anchor, every),
                    )
                ]
            ),
            policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
        ),
    )


async def terminate_workflows_on_undeclared_queues(
    client: Client, declared: frozenset[str]
) -> None:
    """Terminate running work on queues this deployment no longer has.

    `terminate_undeclared_workflows` is scoped to one queue so a worker never touches another's
    work — which is right, and is also why a queue that *lost* its worker is swept by nobody.
    `civicpatch-org-sync` sat that way after the 2026-09-05 split: nothing polled it, so nothing
    ran the sweep for it, so its executions could not be reached by anything but a human.

    This is the namespace-wide half, and belongs to the worker that owns schedules for the same
    reason `register_schedules` does: exactly one owner, or two of them race.

    Each terminate is best-effort. A `Timeout expired` here crashed the worker before it reached
    `Worker(...)` — tidying up an abandoned queue must never stop this one from serving, and an
    orphan that survives is a log line, where a crash-looping worker is an outage.
    """
    async for execution in client.list_workflows("ExecutionStatus='Running'"):
        if execution.task_queue in declared:
            continue
        logger.info(
            "Terminating %s: task queue %s is no longer declared",
            execution.id,
            execution.task_queue,
        )
        try:
            await client.get_workflow_handle(
                execution.id, run_id=execution.run_id
            ).terminate(reason="task queue no longer declared")
        except RPCError:
            logger.exception(
                "Could not terminate %s; leaving it for the next boot", execution.id
            )
