import os
import uuid
from typing import Optional

from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy
from temporalio.service import RPCError, RPCStatusCode

from lib.temporal.types import MergeRequest
from lib.temporal.workflows import (
    RepoMergeQueueWorkflow,
    TASK_QUEUE,
    WorkflowInstanceId,
)
from shared.utils.timeouts import PEOPLE_COLLECTOR_EXECUTION_TIMEOUT

_client: Client | None = None

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "temporal:7233")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")
PEOPLE_COLLECTOR_TASK_QUEUE = "people-collector"
WORKFLOW_CLASS_NAME = "PeopleCollectorWorkflow"


def _workflow_id(jurisdiction_ocdid: str) -> str:
    safe = jurisdiction_ocdid.replace("/", "-").replace(":", "-")
    return f"people-collector-{safe}"


async def _get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(
            TEMPORAL_HOST,
            namespace=TEMPORAL_NAMESPACE,
        )
    return _client


async def start_people_collector_workflow(
    jurisdiction_ocdid: str,
    request_id: str,
    dispatch_mode: str = "remote",
    url: Optional[str] = None,
    source_urls: Optional[list[str]] = None,
) -> str:
    client = await _get_client()
    workflow_id = _workflow_id(jurisdiction_ocdid)
    # TERMINATE_EXISTING cleans up zombie Temporal workflows (e.g. after a worker crash).
    # The frontend is responsible for not calling this endpoint when a job is actively running.
    handle = await client.start_workflow(
        WORKFLOW_CLASS_NAME,
        args=[jurisdiction_ocdid, request_id, dispatch_mode, url, source_urls],
        id=workflow_id,
        task_queue=PEOPLE_COLLECTOR_TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING,
        execution_timeout=PEOPLE_COLLECTOR_EXECUTION_TIMEOUT,
    )
    return handle.id


async def start_batch_people_collector_workflow(state: str, items: list[dict]) -> str:
    client = await _get_client()
    handle = await client.start_workflow(
        "BatchPeopleCollectorWorkflow",
        args=[items],
        id=f"batch-people-collector-{state}-{uuid.uuid4().hex[:8]}",
        task_queue=PEOPLE_COLLECTOR_TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING,
    )
    return handle.id


async def enqueue_merge(request: MergeRequest) -> None:
    """Send a PR merge request to the singleton RepoMergeQueueWorkflow.

    Uses signal-with-start: if the queue workflow is already running, the signal
    is appended to its FIFO; if not, it starts the workflow and delivers the
    signal as the first item."""
    client = await _get_client()
    await client.start_workflow(
        RepoMergeQueueWorkflow.run,
        id=WorkflowInstanceId.REPO_MERGE_QUEUE,
        task_queue=TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        start_signal="enqueue",
        start_signal_args=[request],
    )


async def signal_human_approval(jurisdiction_ocdid: str) -> None:
    client = await _get_client()
    handle = client.get_workflow_handle(_workflow_id(jurisdiction_ocdid))
    await handle.signal("human_approval")


async def cancel_workflow(jurisdiction_ocdid: str) -> None:
    client = await _get_client()
    handle = client.get_workflow_handle(_workflow_id(jurisdiction_ocdid))
    try:
        await handle.cancel()
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            return
        raise
