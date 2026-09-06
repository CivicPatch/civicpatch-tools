"""Expiry workflows: retiring work that time, or a newer arrival, made irrelevant.

Split out of the single `workflows.py` on 2026-09-05. Nothing here touches a sink, so nothing
here should pay to import one.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from routers.temporal.expiry_activities import (
        cleanup_stale_review_entries_activity,
        expire_stale_pipeline_runs_activity,
        supersede_stacked_requests_activity,
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
