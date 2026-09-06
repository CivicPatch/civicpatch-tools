"""Inbound sync workflows: open-data's jurisdiction files into the database.

Split out of the single `workflows.py` on 2026-09-05. The split is what makes the per-worker
import graphs small — a module that imports every activity gives every worker the union of
their dependencies, so splitting the activities alone would have bought nothing.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from routers.temporal.jurisdiction_activities import (
        od_sync_activity,
        od_sync_targeted_activity,
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
class OdSyncTargetedWorkflow:
    @workflow.run
    async def run(self, jurisdiction_ocdids: list[str]) -> None:
        await workflow.execute_activity(
            od_sync_targeted_activity,
            jurisdiction_ocdids,
            start_to_close_timeout=timedelta(minutes=60),
        )
