"""Inbound sync worker, and the one that owns schedule registration.

Registration lives here rather than being shared out because `retire_undeclared_schedules`
deletes anything on the server it does not recognise — four workers each declaring a subset
would delete each other's schedules on every boot. This one declares all five, each naming the
queue that actually serves it; the other three just poll. See `lib/temporal/schedules.py`.
"""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database.database import get_pool
from lib.temporal.schedules import (
    register_schedules,
    terminate_undeclared_workflows,
    terminate_workflows_on_undeclared_queues,
)
from lib.temporal.source_workflows import ReadOpenDataJurisdictionsWorkflow
from lib.temporal.types import SOURCE_TASK_QUEUE, TASK_QUEUES
from routers.temporal.source_activities import (
    read_open_data_jurisdictions_activity,
)
from temporalio.client import Client
from temporalio.worker import Worker

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")

WORKFLOWS = [ReadOpenDataJurisdictionsWorkflow]
ACTIVITIES = [read_open_data_jurisdictions_activity]


async def main() -> None:
    await get_pool()

    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    await register_schedules(client)
    await terminate_workflows_on_undeclared_queues(client, TASK_QUEUES)
    await terminate_undeclared_workflows(
        client, SOURCE_TASK_QUEUE, {workflow.__name__ for workflow in WORKFLOWS}
    )
    async with Worker(
        client,
        task_queue=SOURCE_TASK_QUEUE,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
    ):
        print(f"Worker started on task queue: {SOURCE_TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
