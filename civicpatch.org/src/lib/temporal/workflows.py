from datetime import timedelta
from enum import StrEnum

from temporalio import workflow
from temporalio.common import RetryPolicy

from lib.temporal.types import OpenDataBatchCommitRequest


class ScheduleId(StrEnum):
    OD_SYNC = "od-sync"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup"
    SYNC_SWEEP = "sync-sweep"


class WorkflowInstanceId(StrEnum):
    OD_SYNC = "od-sync-workflow"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup-workflow"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup-workflow"
    REPO_MERGE_QUEUE = "repo-merge-queue"
    SYNC_SWEEP = "sync-sweep-workflow"


with workflow.unsafe.imports_passed_through():
    from routers.temporal.activities import (
        cleanup_stale_review_entries_activity,
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
class SyncSweepWorkflow:
    """Sync whatever changed recently to both outward sinks — the sheet and open-data.

    One sweep, not two: both read the same `change_logs` window, so a second schedule would
    ask the same question of the same rows five minutes out of step.

    Sequential rather than concurrent because a permanent failure in one costs nothing — the
    lookback is wider than the cadence, so the next run sees the same changes again.
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
