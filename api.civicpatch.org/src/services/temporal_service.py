import os

from temporalio.client import Client, WorkflowFailureError
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

_client: Client | None = None

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")
TASK_QUEUE = "people-collector"
WORKFLOW_CLASS_NAME = "PeopleCollectorWorkflow"


def _workflow_id(jurisdiction_ocdid: str) -> str:
    safe = jurisdiction_ocdid.replace("/", "-").replace(":", "-")
    return f"people-collector-{safe}"


async def _get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(TEMPORAL_HOST, namespace=TEMPORAL_NAMESPACE)
    return _client


async def start_people_collector_workflow(jurisdiction_ocdid: str, request_id: str) -> str:
    client = await _get_client()
    workflow_id = _workflow_id(jurisdiction_ocdid)
    handle = await client.start_workflow(
        WORKFLOW_CLASS_NAME,
        args=[jurisdiction_ocdid, request_id],
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )
    return handle.id


async def signal_human_approval(jurisdiction_ocdid: str) -> None:
    client = await _get_client()
    handle = client.get_workflow_handle(_workflow_id(jurisdiction_ocdid))
    await handle.signal("human_approval")


async def cancel_workflow(jurisdiction_ocdid: str) -> None:
    client = await _get_client()
    handle = client.get_workflow_handle(_workflow_id(jurisdiction_ocdid))
    await handle.cancel()
