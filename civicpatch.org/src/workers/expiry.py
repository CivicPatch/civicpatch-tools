"""Expiry worker: retiring work that time, or a newer arrival, made irrelevant.

Cheap and short — stale runs, idle review sessions, superseded changesets. Uncapped, because
none of it materialises anything. Registers no schedules; `workers/jurisdictions.py` owns those.
"""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database.database import get_pool
from lib.temporal.expiry_workflows import (
    PipelineRunCleanupWorkflow,
    ReviewSessionCleanupWorkflow,
)
from lib.temporal.schedules import terminate_undeclared_workflows
from lib.temporal.types import EXPIRY_TASK_QUEUE
from routers.temporal.expiry_activities import (
    cleanup_stale_review_entries_activity,
    expire_stale_pipeline_runs_activity,
    supersede_stacked_requests_activity,
)
from temporalio.client import Client
from temporalio.worker import Worker

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")

WORKFLOWS = [PipelineRunCleanupWorkflow, ReviewSessionCleanupWorkflow]

ACTIVITIES = [
    cleanup_stale_review_entries_activity,
    expire_stale_pipeline_runs_activity,
    supersede_stacked_requests_activity,
]


async def main() -> None:
    await get_pool()

    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    await terminate_undeclared_workflows(
        client, EXPIRY_TASK_QUEUE, {workflow.__name__ for workflow in WORKFLOWS}
    )
    async with Worker(
        client,
        task_queue=EXPIRY_TASK_QUEUE,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
    ):
        print(f"Worker started on task queue: {EXPIRY_TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
