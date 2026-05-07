import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from database.database import get_pool, close_pool
from lib.temporal.map_workflows import SyncJurisdictionMapWorkflow, TASK_QUEUE
from routers.temporal.map_activities import sync_jurisdiction_map_activity

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")


async def main() -> None:
    await get_pool()
    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SyncJurisdictionMapWorkflow],
        activities=[sync_jurisdiction_map_activity],
    ):
        print(f"Map worker started on task queue: {TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
