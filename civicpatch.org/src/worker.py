import asyncio
import logging
import os

logging.basicConfig(level=logging.INFO)

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow, ScheduleOverlapPolicy, SchedulePolicy, ScheduleSpec
from temporalio.service import RPCError, RPCStatusCode
from temporalio.worker import Worker

from activities.sync_activities import sync_pr_state_activity, od_sync_activity
from workflows.sync import PRSyncWorkflow, OdSyncWorkflow, TASK_QUEUE
from database.database import get_pool, close_pool

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")


async def _schedule_exists(client: Client, schedule_id: str) -> bool:
    try:
        await client.get_schedule_handle(schedule_id).describe()
        return True
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            return False
        raise


async def _register_schedules(client: Client) -> None:
    if not await _schedule_exists(client, "pr-sync"):
        await client.create_schedule(
            "pr-sync",
            Schedule(
                action=ScheduleActionStartWorkflow(
                    PRSyncWorkflow.run,
                    id="pr-sync-workflow",
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(cron_expressions=["0 * * * *"]),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
            ),
        )

    if not await _schedule_exists(client, "od-sync"):
        handle = await client.create_schedule(
            "od-sync",
            Schedule(
                action=ScheduleActionStartWorkflow(
                    OdSyncWorkflow.run,
                    id="od-sync-workflow",
                    task_queue=TASK_QUEUE,
                ),
                spec=ScheduleSpec(cron_expressions=["0 0 * * *"]),
                policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.SKIP),
            ),
        )
        await handle.trigger()


async def main() -> None:
    await get_pool()
    client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    await _register_schedules(client)
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[PRSyncWorkflow, OdSyncWorkflow],
        activities=[sync_pr_state_activity, od_sync_activity],
    ):
        print(f"Worker started on task queue: {TASK_QUEUE}")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
