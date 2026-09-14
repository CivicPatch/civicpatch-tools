"""Expiry worker: retiring work that time, or a newer arrival, made irrelevant.

Cheap and short — stale runs, idle review sessions, superseded changesets. Uncapped, because
none of it materialises anything. Registers no schedules; `workers/source.py` owns those.
"""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from database.database import get_pool
from lib.temporal.cleanup_workflows import (
    CleanupPipelineRunsWorkflow,
    CleanupReviewSessionsWorkflow,
)
from lib.temporal.connection import connect_with_retry, run_worker
from lib.temporal.schedules import terminate_undeclared_workflows
from lib.temporal.types import CLEANUP_TASK_QUEUE
from routers.temporal.cleanup_activities import (
    cleanup_stale_review_entries_activity,
    expire_stale_pipeline_runs_activity,
    supersede_stacked_requests_activity,
)

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")

WORKFLOWS = [CleanupPipelineRunsWorkflow, CleanupReviewSessionsWorkflow]

ACTIVITIES = [
    cleanup_stale_review_entries_activity,
    expire_stale_pipeline_runs_activity,
    supersede_stacked_requests_activity,
]


async def main() -> None:
    await get_pool()

    client = await connect_with_retry(TEMPORAL_HOST, TEMPORAL_NAMESPACE)
    await terminate_undeclared_workflows(
        client, CLEANUP_TASK_QUEUE, {workflow.__name__ for workflow in WORKFLOWS}
    )
    await run_worker(client, CLEANUP_TASK_QUEUE, WORKFLOWS, ACTIVITIES)


if __name__ == "__main__":
    asyncio.run(main())
