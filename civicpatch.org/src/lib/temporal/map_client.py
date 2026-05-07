import os
from typing import Optional

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy

from lib.temporal.map_workflows import SyncJurisdictionMapWorkflow, TASK_QUEUE

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")

_client: Client | None = None


async def _get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    return _client


async def start_sync_jurisdiction_map_workflow(state: Optional[str] = None) -> str:
    client = await _get_client()
    workflow_id = f"sync-jurisdiction-map-{state or 'all'}"
    handle = await client.start_workflow(
        SyncJurisdictionMapWorkflow.run,
        args=[state],
        id=workflow_id,
        task_queue=TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING,
    )
    return handle.id
