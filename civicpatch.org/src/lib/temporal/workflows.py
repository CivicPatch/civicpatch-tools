from datetime import timedelta
from enum import StrEnum

from temporalio import workflow


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


with workflow.unsafe.imports_passed_through():
    from routers.temporal.activities import (
        sync_pr_state_activity,
        od_sync_activity,
        expire_stale_pipeline_runs_activity,
        cleanup_stale_review_entries_activity,
    )

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
