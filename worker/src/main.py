import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from activities.github_activity import trigger_github_action, poll_run_status, trigger_local_job, poll_local_job_status
from activities.job_status_activity import update_job_status
from workflows.people_collector import PeopleCollectorWorkflow, TASK_QUEUE

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")


async def main() -> None:
    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[PeopleCollectorWorkflow],
        activities=[trigger_github_action, poll_run_status, trigger_local_job, poll_local_job_status, update_job_status],
    ):
        print(f"Worker started on task queue: {TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
