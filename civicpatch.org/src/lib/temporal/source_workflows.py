"""Inbound: open-data's jurisdiction files read into the database.

Split out of the single `workflows.py` on 2026-09-05. The split is what makes the per-worker
import graphs small — a module that imports every activity gives every worker the union of
their dependencies, so splitting the activities alone would have bought nothing.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from routers.temporal.source_activities import read_open_data_jurisdictions_activity


@workflow.defn
class ReadOpenDataJurisdictionsWorkflow:
    @workflow.run
    async def run(self) -> None:
        await workflow.execute_activity(
            read_open_data_jurisdictions_activity,
            start_to_close_timeout=timedelta(minutes=60),
        )
