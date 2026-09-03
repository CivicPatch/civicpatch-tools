from datetime import timedelta
from enum import StrEnum

from temporalio import workflow
from temporalio.common import RetryPolicy

from lib.temporal.types import OpenDataBatchCommitRequest, OpenDataCommitRequest


class ScheduleId(StrEnum):
    OD_SYNC = "od-sync"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup"
    ROSTER_SHEET_SWEEP = "roster-sheet-sweep"


class WorkflowInstanceId(StrEnum):
    OD_SYNC = "od-sync-workflow"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup-workflow"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup-workflow"
    REPO_MERGE_QUEUE = "repo-merge-queue"
    ROSTER_SHEET_SWEEP = "roster-sheet-sweep-workflow"


with workflow.unsafe.imports_passed_through():
    from routers.temporal.activities import (
        cleanup_stale_review_entries_activity,
        commit_open_data_activity,
        commit_open_data_batch_activity,
        expire_stale_pipeline_runs_activity,
        od_sync_activity,
        od_sync_targeted_activity,
        supersede_stacked_requests_activity,
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
class RosterSheetSweepWorkflow:
    """Sync whatever changed recently. The sheet's only route in during normal running."""

    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            sweep_roster_sheets_activity,
            start_to_close_timeout=timedelta(minutes=5),
        )


@workflow.defn
class OpenDataCommitWorkflow:
    """Write one file into open-data, durably.

    Unlike RepoMergeQueueWorkflow this is not a queue. A merge raced every other merge on one
    shared base branch, so they had to be serialised repo-wide; a Contents-API write conflicts
    only with writes to the *same file*, and the workflow id is that file's path — so same-file
    writes serialise and everything else runs concurrently.

    It also retries, which merging could not: the activity re-renders from the database and
    overwrites, so running it twice is the same as running it once.
    """

    @workflow.run
    async def run(self, request: OpenDataCommitRequest) -> None:
        await workflow.execute_activity(
            commit_open_data_activity,
            request,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                backoff_coefficient=2.0,
                maximum_interval=timedelta(minutes=10),
                # Unlimited: the database already says this is published, so the write has to
                # happen eventually. Capping attempts would turn a long GitHub outage into
                # data that is live in the app but missing from open-data, with nothing left
                # to make it land. Retrying is safe because the activity re-renders.
                maximum_attempts=0,
                # A malformed request will never succeed, so it fails fast instead of
                # retrying for days.
                non_retryable_error_types=["ValueError"],
            ),
        )


@workflow.defn
class OpenDataBatchCommitWorkflow:
    """Write every jurisdiction a bulk publish made live, as one commit.

    Same durability as `OpenDataCommitWorkflow` — the activity re-renders from the database, so
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
