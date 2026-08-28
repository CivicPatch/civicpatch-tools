import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy
from temporalio.service import RPCError, RPCStatusCode

from core.temporal_workflow_state import TemporalWorkflowState, summarize
from lib.temporal.types import OpenDataBatchCommitRequest, OpenDataCommitRequest
from lib.temporal.workflows import (
    OdSyncTargetedWorkflow,
    OpenDataBatchCommitWorkflow,
    OpenDataCommitWorkflow,
    ScheduleId,
    TASK_QUEUE,
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


async def trigger_full_od_sync() -> None:
    """Run a full open-data sync now by triggering the existing OD_SYNC schedule, so manual
    and cron syncs share one durable path. The schedule's overlap policy + the singleton
    workflow id keep it from running concurrently with an in-flight sync."""
    client = await _get_client()
    await client.get_schedule_handle(ScheduleId.OD_SYNC).trigger()


async def start_targeted_od_sync(jurisdiction_ocdids: list[str]) -> str:
    client = await _get_client()
    handle = await client.start_workflow(
        OdSyncTargetedWorkflow.run,
        args=[jurisdiction_ocdids],
        id=f"od-sync-targeted-{uuid.uuid4().hex[:8]}",
        task_queue=TASK_QUEUE,
    )
    return handle.id




async def enqueue_open_data_commit(request: OpenDataCommitRequest) -> None:
    """Queue a durable write of one file into open-data.

    The workflow id is the file path, so two writes to the same file serialise while writes to
    different files run concurrently — the conflict domain of a Contents-API write is one blob,
    not the branch. USE_EXISTING means a write queued while one is already running for that
    file is dropped rather than duplicated: the running attempt renders from the database, so
    it will pick up the newer content anyway.
    """
    client = await _get_client()
    await client.start_workflow(
        OpenDataCommitWorkflow.run,
        request,
        id=f"open-data-commit:{request.file_path}",
        task_queue=TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def enqueue_open_data_batch_commit(request: OpenDataBatchCommitRequest) -> None:
    """Queue a durable write of one commit covering every jurisdiction in the request.

    The workflow id covers the batch *and* what was selected, not the batch alone: a reviewer
    who publishes ten towns and then ten more has done two things, and keying on the batch
    would let USE_EXISTING drop the second. Identical selections still dedupe, which is what
    makes a double-clicked Publish harmless.
    """
    client = await _get_client()
    selection = ",".join(sorted(item.request_id for item in request.items))
    digest = hashlib.sha256(selection.encode()).hexdigest()[:12]
    await client.start_workflow(
        OpenDataBatchCommitWorkflow.run,
        request,
        id=f"open-data-batch-commit:{request.batch_id}:{digest}",
        task_queue=TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def signal_human_approval(jurisdiction_ocdid: str) -> None:
    client = await _get_client()
    handle = client.get_workflow_handle(_workflow_id(jurisdiction_ocdid))
    await handle.signal("human_approval")


async def describe_workflow(jurisdiction_ocdid: str) -> TemporalWorkflowState | None:
    """What this jurisdiction's scrape workflow is doing right now.

    None when there is no workflow, it has finished, or it is between activities. All three
    mean "nothing to say", and the caller renders nothing — the block only exists to explain
    a run that is in flight.

    Read live rather than stored: this is true for seconds at a time, and a stored copy would
    be a stale answer to a question only worth asking about the present.
    """
    client = await _get_client()
    handle = client.get_workflow_handle(_workflow_id(jurisdiction_ocdid))
    try:
        description = await handle.describe()
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            return None
        raise

    if description.status != WorkflowExecutionStatus.RUNNING:
        return None

    pending = [
        {
            "activity_type": a.activity_type.name if a.activity_type else None,
            "attempt": a.attempt,
            "scheduled_time": a.scheduled_time.ToDatetime() if a.HasField("scheduled_time") else None,
            "last_failure": a.last_failure if a.HasField("last_failure") else None,
        }
        for a in description.raw_description.pending_activities
    ]
    return summarize(pending, datetime.now(timezone.utc))


async def cancel_workflow(jurisdiction_ocdid: str) -> None:
    client = await _get_client()
    handle = client.get_workflow_handle(_workflow_id(jurisdiction_ocdid))
    try:
        await handle.cancel()
    except RPCError as e:
        if e.status == RPCStatusCode.NOT_FOUND:
            return
        raise
