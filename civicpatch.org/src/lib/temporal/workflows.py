from datetime import timedelta
from enum import StrEnum

from temporalio import workflow
from temporalio.common import RetryPolicy

from lib.temporal.types import OpenDataBatchCommitRequest


class ScheduleId(StrEnum):
    OD_SYNC = "od-sync"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup"
    SWEEP_CHANGES = "sweep-changes"
    SWEEP_EVERYTHING = "sweep-everything"


class WorkflowInstanceId(StrEnum):
    OD_SYNC = "od-sync-workflow"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup-workflow"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup-workflow"
    REPO_MERGE_QUEUE = "repo-merge-queue"
    SWEEP_CHANGES = "sweep-changes-workflow"
    SWEEP_EVERYTHING = "sweep-everything-workflow"


with workflow.unsafe.imports_passed_through():
    from routers.temporal.activities import (
        backstop_open_data_activity,
        sync_roster_parquet_activity,
        cleanup_stale_review_entries_activity,
        list_states_activity,
        commit_open_data_batch_activity,
        expire_stale_pipeline_runs_activity,
        od_sync_activity,
        od_sync_targeted_activity,
        supersede_stacked_requests_activity,
        sweep_open_data_activity,
        sweep_roster_sheets_activity,
        sync_jurisdictions_sheet_activity,
        sync_roster_sheet_activity,
    )

TASK_QUEUE = "civicpatch-org-sync"

# Bound history growth: after this many merges, continue-as-new with the remaining queue.
# 500 keeps history well under Temporal's recommended 10k-event ceiling.
_CONTINUE_AS_NEW_THRESHOLD = 500


@workflow.defn
class OdSyncWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            od_sync_activity,
            start_to_close_timeout=timedelta(minutes=60),
        )


@workflow.defn
class OdSyncTargetedWorkflow:
    @workflow.run
    async def run(self, jurisdiction_ocdids: list[str]) -> None:
        await workflow.execute_activity(
            od_sync_targeted_activity,
            jurisdiction_ocdids,
            start_to_close_timeout=timedelta(minutes=60),
        )


@workflow.defn
class PipelineRunCleanupWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            expire_stale_pipeline_runs_activity,
            start_to_close_timeout=timedelta(minutes=5),
        )


@workflow.defn
class ReviewSessionCleanupWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            cleanup_stale_review_entries_activity,
            start_to_close_timeout=timedelta(minutes=5),
        )
        await workflow.execute_activity(
            supersede_stacked_requests_activity,
            start_to_close_timeout=timedelta(minutes=5),
        )


# Long enough to collapse a state scrape's town-by-town publishing into one tab rewrite.
_SHEET_DEBOUNCE = timedelta(seconds=60)

# Bounds history, as the merge queue does.
_SHEET_SYNC_MAX_PASSES = 50

# Retried forever, like the open-data commits. Safe: the activity replaces the tab from current
# truth rather than replaying.
_SHEET_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=10),
    maximum_attempts=0,
    # A deployment problem, not a transient one. Retrying for days would hide it.
    non_retryable_error_types=["SheetNotConfigured", "SheetsNotConfigured", "ValueError"],
)


@workflow.defn
class RosterSheetSyncWorkflow:
    """Rewrite one state's tabs, coalescing everything that asks while it waits.

    Started with `start_signal`, never `USE_EXISTING`: a dropped request between the activity's
    read and this closing is a lost update no later publish would repair.
    """

    def __init__(self) -> None:
        # True so a plain start syncs once; the signal re-sets it on every later pass.
        self._dirty = True

    @workflow.signal
    def mark_dirty(self) -> None:
        self._dirty = True

    @workflow.run
    async def run(self, state: str) -> None:
        for _ in range(_SHEET_SYNC_MAX_PASSES):
            if not self._dirty:
                return
            # Cleared before the wait: clearing after the activity would swallow anything
            # that arrived during it.
            self._dirty = False
            await workflow.sleep(_SHEET_DEBOUNCE)
            await workflow.execute_activity(
                sync_roster_sheet_activity,
                state,
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=_SHEET_RETRY,
            )
        workflow.continue_as_new(state)


@workflow.defn
class JurisdictionsSheetSyncWorkflow:
    """Rewrite the all-states dropdown source. Triggered by od_sync, but its own workflow —
    that schedule is SKIP-overlap and a forever-retrying write would wedge it."""

    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            sync_jurisdictions_sheet_activity,
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=_SHEET_RETRY,
        )


@workflow.defn
class SweepChangesWorkflow:
    """Every 5 minutes: what `change_logs` saw in the last 15, to both sinks.

    Named for its scope rather than its cadence — the cadence is a cron string that may change,
    while "only what changed" is the definition. `SweepEverythingWorkflow` is the other half.

    One sweep, not two: both sinks read the same `change_logs` window, so a second schedule would
    ask the same question of the same rows five minutes out of step.

    Sequential rather than concurrent because a permanent failure in one costs nothing — the
    lookback is wider than the cadence, so the next run sees the same changes again. That
    argument does not carry over to the daily sweep, where the next run is 24 hours away.
    """

    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            sweep_roster_sheets_activity,
            start_to_close_timeout=timedelta(minutes=5),
        )
        await workflow.execute_activity(
            sweep_open_data_activity,
            start_to_close_timeout=timedelta(minutes=5),
        )


@workflow.defn
class SweepEverythingWorkflow:
    """Once a day: every state and every jurisdiction, whatever `change_logs` said.

    The backstop. `SweepChangesWorkflow` only ever sees what the feed reports, so a write path
    that skips it or an activity that fails non-retryably leaves a mirror stale forever. Nothing
    else notices.

    Affordable only because of the content gate — an unchanged state renders, hashes, matches,
    and makes no API call. Without it this would rewrite every tab and every file nightly.

    Ordered by who is looking. The two mirrors people read come first; anything analytical goes
    last, so its failure cannot delay them. For the same reason a step added here must have
    bounded retries: retrying forever would leave this workflow open, and the schedule's
    `SKIP` overlap policy would then suppress tomorrow's backstop entirely.
    """

    @workflow.run
    async def run(self) -> None:
        # One state at a time, not fifteen at once. Google Sheets allows 60 write requests a
        # minute for the whole service account, and a full pass is ~192 — fanned out they all
        # 429, back off, and the unlucky ones exhaust their activity timeout without having been
        # slow. Sequential cannot exceed the quota and takes about four minutes, which a nightly
        # backstop has.
        #
        # Still one activity per state, so each keeps its own timeout and retry: a state that
        # genuinely fails does not take the other fourteen with it.
        for state in await workflow.execute_activity(
            list_states_activity,
            start_to_close_timeout=timedelta(minutes=1),
        ):
            await workflow.execute_activity(
                sync_roster_sheet_activity,
                state,
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=_SHEET_RETRY,
            )
        await workflow.execute_activity(
            backstop_open_data_activity,
            start_to_close_timeout=timedelta(minutes=15),
        )
        # Bounded, unlike the mirrors. Retrying forever would leave this workflow open and the
        # schedule's SKIP policy would then suppress tomorrow's backstop entirely — the mirrors
        # would quietly stop being checked because a dump nobody is waiting on could not write.
        await workflow.execute_activity(
            sync_roster_parquet_activity,
            start_to_close_timeout=timedelta(minutes=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


@workflow.defn
class OpenDataBatchCommitWorkflow:
    """Write every jurisdiction a bulk publish made live, as one commit.

    The activity re-renders every file from the database on each attempt, so
    retrying is safe and worth doing forever. What differs is the conflict domain: this moves
    the branch ref rather than one blob, so two batches racing means one loses the fast-forward
    and retries against the other's commit.
    """

    @workflow.run
    async def run(self, request: OpenDataBatchCommitRequest) -> None:
        await workflow.execute_activity(
            commit_open_data_batch_activity,
            request,
            # Longer than the single-file write: this renders one roster per jurisdiction
            # before it writes anything.
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(minutes=10),
                maximum_attempts=0,
                non_retryable_error_types=["ValueError"],
            ),
        )
