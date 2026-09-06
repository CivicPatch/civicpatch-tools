"""Temporal worker for the scrape queue. Same image as `sinks.py`, its own process and pod.

Separate from `sinks.py` so it keeps the narrow secret scope its old standalone image had —
secrets are granted per Deployment, not per image — and so a sweep that dies cannot take scrape
dispatch with it.

**Keep the imports below minimal.** This entrypoint measures 63MiB because nothing here pulls
`database` or `services`; adding either drags in pyarrow, boto3, gspread and psycopg and roughly
doubles it. Nothing on this queue touches the database — every activity goes over HTTP.
"""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from lib.temporal.scrape_workflows import (
    BatchPeopleCollectorWorkflow,
    PeopleCollectorWorkflow,
    StateScrapeWorkflow,
)
from lib.temporal.types import SCRAPE_TASK_QUEUE
from routers.temporal.scrape_activities import (
    cancel_local_run,
    claim_scrape_candidates,
    poll_pipeline_run_status,
    trigger_github_action,
    trigger_local,
    update_pipeline_run_status,
)
from temporalio.client import Client
from temporalio.worker import Worker

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")

WORKFLOWS = [
    PeopleCollectorWorkflow,
    BatchPeopleCollectorWorkflow,
    StateScrapeWorkflow,
]

ACTIVITIES = [
    trigger_github_action,
    trigger_local,
    cancel_local_run,
    poll_pipeline_run_status,
    update_pipeline_run_status,
    claim_scrape_candidates,
]

# Deliberately uncapped, unlike `sinks.py`: `poll_pipeline_run_status` holds a slot for up to
# 35 minutes and a state scrape dispatches 25 children at a time, so a small cap would serialise
# a scrape into 35-minute batches. These activities are sleeping HTTP clients, not memory.


async def connect_with_retry(
    host: str, namespace: str, retries: int = 10, delay: float = 3.0
) -> Client:
    for attempt in range(1, retries + 1):
        try:
            return await Client.connect(host, namespace=namespace)
        except Exception as e:
            if attempt == retries:
                raise
            print(
                f"Temporal not ready (attempt {attempt}/{retries}): {e} — retrying in {delay}s"
            )
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


async def main() -> None:
    client = await connect_with_retry(TEMPORAL_HOST, TEMPORAL_NAMESPACE)
    async with Worker(
        client,
        task_queue=SCRAPE_TASK_QUEUE,
        workflows=WORKFLOWS,
        activities=ACTIVITIES,
    ):
        print(f"Worker started on task queue: {SCRAPE_TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
