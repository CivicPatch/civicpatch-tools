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

from lib.temporal.connection import connect_with_retry, run_worker
from lib.temporal.governing_law_collector_workflows import (
    GoverningLawCollectorWorkflow,
    GoverningLawCollectorStateWorkflow,
)
from lib.temporal.pipeline_run_workflows import (
    PeopleCollectorWorkflow,
    PeopleCollectorStateWorkflow,
)
from lib.temporal.types import PIPELINE_RUNS_TASK_QUEUE
from routers.temporal.governing_law_collector_activities import (
    claim_jurisdictions_for_governing_law_collector,
    governing_law_collector_month_cap_reached,
    trigger_governing_law_collector_local,
    trigger_governing_law_collector_remote,
)
from routers.temporal.pipeline_run_activities import (
    people_collector_month_cap_reached,
    cancel_local_pipeline_run,
    claim_jurisdictions_for_people_collector,
    poll_pipeline_run_status,
    trigger_people_collector_remote,
    trigger_people_collector_local,
    update_pipeline_run_status,
)

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")

WORKFLOWS = [
    PeopleCollectorWorkflow,
    PeopleCollectorStateWorkflow,
    GoverningLawCollectorWorkflow,
    GoverningLawCollectorStateWorkflow,
]

ACTIVITIES = [
    people_collector_month_cap_reached,
    trigger_people_collector_remote,
    trigger_people_collector_local,
    cancel_local_pipeline_run,
    poll_pipeline_run_status,
    update_pipeline_run_status,
    claim_jurisdictions_for_people_collector,
    claim_jurisdictions_for_governing_law_collector,
    governing_law_collector_month_cap_reached,
    trigger_governing_law_collector_local,
    trigger_governing_law_collector_remote,
]

# Deliberately uncapped, unlike `sinks.py`: `poll_pipeline_run_status` holds a slot for up to
# 35 minutes and a state scrape dispatches 25 children at a time, so a small cap would serialise
# a scrape into 35-minute batches. These activities are sleeping HTTP clients, not memory.


async def main() -> None:
    client = await connect_with_retry(TEMPORAL_HOST, TEMPORAL_NAMESPACE)
    await run_worker(client, PIPELINE_RUNS_TASK_QUEUE, WORKFLOWS, ACTIVITIES)


if __name__ == "__main__":
    asyncio.run(main())
