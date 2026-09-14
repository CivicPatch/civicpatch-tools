"""Temporal worker for the maps queue. Same image as the other three workers — a separate
container/pod so tippecanoe/geopandas/pyogrio (heavy, single-purpose) don't ride along on
every deploy of the lean workers, and so a wedged map build can't take anything else down
with it.
"""

import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from lib.temporal.connection import connect_with_retry, run_worker
from lib.temporal.map_generation_workflows import GenerateMapsWorkflow
from lib.temporal.types import MAPS_TASK_QUEUE
from routers.temporal.map_generation_activities import (
    build_and_upload_national_overview,
    build_and_upload_state_pmtiles,
)

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")

# Temporal defaults to 100. Each activity here is one blocking pipeline (TIGER fetch,
# geopandas, tippecanoe) on one pod — a manual trigger for several states at once
# shouldn't try to run them all in parallel.
MAX_CONCURRENT_ACTIVITIES = 2

WORKFLOWS = [
    GenerateMapsWorkflow,
]

ACTIVITIES = [
    build_and_upload_state_pmtiles,
    build_and_upload_national_overview,
]


async def main() -> None:
    client = await connect_with_retry(TEMPORAL_HOST, TEMPORAL_NAMESPACE)
    await run_worker(client, MAPS_TASK_QUEUE, WORKFLOWS, ACTIVITIES, MAX_CONCURRENT_ACTIVITIES)


if __name__ == "__main__":
    asyncio.run(main())
