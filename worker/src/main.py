import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from activities.github_activity import trigger_github_action, trigger_local
from activities.pipeline_run_status_activity import update_pipeline_run_status, poll_pipeline_run_status
from workflows.people_collector import BatchPeopleCollectorWorkflow, PeopleCollectorWorkflow, TASK_QUEUE

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")


async def connect_with_retry(host: str, namespace: str, retries: int = 10, delay: float = 3.0) -> Client:
    for attempt in range(1, retries + 1):
        try:
            return await Client.connect(host, namespace=namespace)
        except Exception as e:
            if attempt == retries:
                raise
            print(f"Temporal not ready (attempt {attempt}/{retries}): {e} — retrying in {delay}s")
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")


async def main() -> None:
    client = await connect_with_retry(TEMPORAL_HOST, TEMPORAL_NAMESPACE)
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[PeopleCollectorWorkflow, BatchPeopleCollectorWorkflow],
        activities=[trigger_github_action, trigger_local, poll_pipeline_run_status, update_pipeline_run_status],
    ):
        print(f"Worker started on task queue: {TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
