"""
Spike worker — starts a Temporal worker and optionally kicks off a workflow.

Usage:
    # Start a new workflow for a jurisdiction:
    python worker.py --jurisdiction-ocdid "ocd-division/country:us/state:ca/place:oakland" --request-id "spike-001"

    # Just run the worker (to resume a suspended workflow after a signal):
    python worker.py

    # Send a human_approval signal to a suspended workflow:
    python worker.py --signal "spike-people-collector-<jurisdiction>"
"""

import argparse
import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from activities import trigger_github_action, poll_run_status
from workflow import PeopleCollectorWorkflow

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = "spike-people-collector"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--jurisdiction-ocdid", default=None)
    parser.add_argument("--request-id", default=None)
    parser.add_argument("--signal", default=None, help="Workflow ID to send human_approval signal to")
    args = parser.parse_args()

    client = await Client.connect(TEMPORAL_HOST)

    # Send signal mode — just signal and exit, no worker needed
    if args.signal:
        handle = client.get_workflow_handle(args.signal)
        await handle.signal(PeopleCollectorWorkflow.human_approval)
        print(f"Sent human_approval signal to workflow: {args.signal}")
        return

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[PeopleCollectorWorkflow],
        activities=[trigger_github_action, poll_run_status],
    ):
        print(f"Worker started on task queue: {TASK_QUEUE}")

        if args.jurisdiction_ocdid and args.request_id:
            safe_id = args.jurisdiction_ocdid.replace("/", "-").replace(":", "-")
            workflow_id = f"spike-people-collector-{safe_id}"

            handle = await client.start_workflow(
                PeopleCollectorWorkflow.run,
                args=[args.jurisdiction_ocdid, args.request_id],
                id=workflow_id,
                task_queue=TASK_QUEUE,
            )
            print(f"Workflow started: {workflow_id}")
            print(f"View in Temporal Web UI: http://localhost:8233/namespaces/default/workflows/{workflow_id}")

        # Keep worker running until Ctrl+C
        print("Worker running — press Ctrl+C to stop")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
