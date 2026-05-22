from datetime import timedelta
from enum import StrEnum

from temporalio import workflow
from temporalio.common import RetryPolicy

from lib.temporal.types import MergeRequest


class ScheduleId(StrEnum):
    PR_SYNC = "pr-sync"
    OD_SYNC = "od-sync"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup"


class WorkflowInstanceId(StrEnum):
    PR_SYNC = "pr-sync-workflow"
    OD_SYNC = "od-sync-workflow"
    PIPELINE_RUN_CLEANUP = "pipeline-run-cleanup-workflow"
    REVIEW_SESSION_CLEANUP = "review-session-cleanup-workflow"
    REPO_MERGE_QUEUE = "repo-merge-queue"


with workflow.unsafe.imports_passed_through():
    from routers.temporal.activities import (
        cleanup_stale_review_entries_activity,
        expire_stale_pipeline_runs_activity,
        merge_pr_activity,
        od_sync_activity,
        sync_pr_state_activity,
    )

TASK_QUEUE = "civicpatch-org-sync"

# Bound history growth: after this many merges, continue-as-new with the remaining queue.
# 500 keeps history well under Temporal's recommended 10k-event ceiling.
_CONTINUE_AS_NEW_THRESHOLD = 500


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


@workflow.defn
class RepoMergeQueueWorkflow:
    """Singleton workflow that serializes PR merges into the open-data repo.

    Concurrent merges race on the shared base branch: GitHub returns "base branch was
    modified" when two PRs merge in quick succession. Funnelling every merge through
    one workflow eliminates the race by construction — only one merge activity runs
    at a time."""

    def __init__(self) -> None:
        self._queue: list[MergeRequest] = []
        self._processed_count = 0

    @workflow.signal
    async def enqueue(self, request: MergeRequest) -> None:
        self._queue.append(request)

    @workflow.run
    async def run(self, initial_queue: list[MergeRequest] | None = None) -> None:
        if initial_queue:
            self._queue.extend(initial_queue)

        while True:
            await workflow.wait_condition(lambda: len(self._queue) > 0)

            if self._processed_count >= _CONTINUE_AS_NEW_THRESHOLD:
                workflow.continue_as_new(args=[list(self._queue)])

            request = self._queue.pop(0)
            try:
                # maximum_attempts=1: do_merge writes its own outcome to Redis and
                # never raises, so the only way a retry would fire is on worker
                # crash mid-activity. Re-running do_merge after a partial merge
                # would see the PR already-merged and write a false "error" to Redis.
                await workflow.execute_activity(
                    merge_pr_activity,
                    request,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=RetryPolicy(maximum_attempts=1),
                )
            except Exception as e:
                # do_merge writes error state to Redis itself; we just log so the
                # queue keeps draining if a single PR's activity raises unexpectedly.
                workflow.logger.error(
                    f"merge_pr_activity failed for PR {request.pull_request_number}: {e}"
                )
            self._processed_count += 1
