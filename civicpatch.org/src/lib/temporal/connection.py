import asyncio

from temporalio.client import Client
from temporalio.worker import Worker


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


async def run_worker(
    client: Client,
    task_queue: str,
    workflows: list,
    activities: list,
    max_concurrent_activities: int | None = None,
) -> None:
    kwargs = {}
    if max_concurrent_activities is not None:
        kwargs["max_concurrent_activities"] = max_concurrent_activities
    async with Worker(
        client, task_queue=task_queue, workflows=workflows, activities=activities, **kwargs
    ):
        print(f"Worker started on task queue: {task_queue}")
        await asyncio.Event().wait()
