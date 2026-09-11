"""Sink worker: the database rendered outward into the sheet, open-data and parquet.

The heavy one. Its activities materialise whole tables — a full sweep peaks around 253Mi
measured — which is why this is the only worker that caps concurrency. Registers no schedules;
`workers/source.py` owns those for the whole namespace.
"""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database.database import get_pool
from lib.temporal.schedules import terminate_undeclared_workflows
from lib.temporal.sink_workflows import (
    WriteSheetJurisdictionsWorkflow,
    WriteOpenDataBatchWorkflow,
    WriteSheetRosterWorkflow,
    WriteRecentChangesWorkflow,
    WriteEverythingWorkflow,
    WriteActivityFeedWorkflow,
)
from lib.temporal.types import SINKS_TASK_QUEUE
from routers.temporal.sink_activities import (
    write_open_data_state_activity,
    write_open_data_batch_activity,
    list_states_activity,
    dispatch_open_data_changes_activity,
    dispatch_sheet_changes_activity,
    write_sheet_jurisdictions_activity,
    write_parquet_roster_activity,
    write_sheet_roster_activity,
    write_activity_feed_activity,
)
from temporalio.client import Client
from temporalio.worker import Worker

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")

# Temporal defaults to 100. These activities materialise whole tables — the sweep peaks at 253Mi.
MAX_CONCURRENT_ACTIVITIES = 5

WORKFLOWS = [
    WriteSheetJurisdictionsWorkflow,
    WriteOpenDataBatchWorkflow,
    WriteSheetRosterWorkflow,
    WriteRecentChangesWorkflow,
    WriteEverythingWorkflow,
    WriteActivityFeedWorkflow,
]

ACTIVITIES = [
    write_open_data_state_activity,
    write_open_data_batch_activity,
    list_states_activity,
    dispatch_open_data_changes_activity,
    dispatch_sheet_changes_activity,
    write_sheet_jurisdictions_activity,
    write_parquet_roster_activity,
    write_sheet_roster_activity,
    write_activity_feed_activity,
]


async def main() -> None:
    await get_pool()

    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    await terminate_undeclared_workflows(
        client, SINKS_TASK_QUEUE, {workflow.__name__ for workflow in WORKFLOWS}
    )
    async with Worker(
        client,
        task_queue=SINKS_TASK_QUEUE,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
        max_concurrent_activities=MAX_CONCURRENT_ACTIVITIES,
    ):
        print(f"Worker started on task queue: {SINKS_TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
