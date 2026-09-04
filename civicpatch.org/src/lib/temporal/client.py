import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.common import WorkflowIDConflictPolicy
from temporalio.service import RPCError, RPCStatusCode

from core.temporal_workflow_state import TemporalWorkflowState, summarize
from lib.temporal.types import OpenDataBatchCommitRequest
from lib.temporal.workflows import (
    JurisdictionsSheetSyncWorkflow,
    OdSyncTargetedWorkflow,
    OpenDataBatchCommitWorkflow,
    RosterSheetSyncWorkflow,
    ScheduleId,
    TASK_QUEUE,
)
from shared.utils.timeouts import PEOPLE_COLLECTOR_EXECUTION_TIMEOUT
from environment import get_env_vars

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
    changeset_id: str,
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
        args=[jurisdiction_ocdid, changeset_id, dispatch_mode, url, source_urls],
        id=workflow_id,
        task_queue=PEOPLE_COLLECTOR_TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.TERMINATE_EXISTING,
        execution_timeout=PEOPLE_COLLECTOR_EXECUTION_TIMEOUT,
    )
    return handle.id


def _pipeline_run_concurrency() -> int:
    """How many pipeline runs may be in flight at once. Read here rather than in the workflow,
    which Temporal replays — a value that changed between runs would diverge."""
    return int(get_env_vars()["PIPELINE_RUN_CONCURRENCY"])


async def start_state_scrape_workflow(
    state: str,
    num_jurisdictions: int | None = None,
    created_by_user_id: str | None = None,
) -> str:
    """One durable workflow per state. It finds its own candidates.

    The id carries no random suffix, which is the point: the previous
    `batch-people-collector-{state}-{uuid}` was unique on every call, so
    `TERMINATE_EXISTING` never fired and two clicks ran two overlapping batches over the same
    candidate pool. Keyed on the state alone, `FAIL` makes a second start an error the caller
    sees rather than a silent duplicate.
    """
    client = await _get_client()
    handle = await client.start_workflow(
        "StateScrapeWorkflow",
        args=[state, num_jurisdictions, created_by_user_id, _pipeline_run_concurrency()],
        id=f"state-scrape-{state}",
        task_queue=PEOPLE_COLLECTOR_TASK_QUEUE,
        id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
    )
    return handle.id


async def start_targeted_od_sync(jurisdiction_ocdids: list[str]) -> str:
    client = await _get_client()
    handle = await client.start_workflow(
        OdSyncTargetedWorkflow.run,
        args=[jurisdiction_ocdids],
        id=f"od-sync-targeted-{uuid.uuid4().hex[:8]}",
        task_queue=TASK_QUEUE,
    )
    return handle.id




async def enqueue_roster_sheet_sync(state: str) -> None:
    """Ask for one state's sheet tabs to be rewritten.

    Signal-with-start, not `USE_EXISTING`. A request arriving while the workflow runs must not
    be dropped — between the activity's read and the workflow closing, a drop is a lost update
    that only the next publish in that state would repair. Signalling instead earns another
    pass; see `RosterSheetSyncWorkflow`.
    """
    client = await _get_client()
    await client.start_workflow(
        RosterSheetSyncWorkflow.run,
        state,
        id=f"roster-sheet-sync:{state}",
        task_queue=TASK_QUEUE,
        start_signal="mark_dirty",
    )


async def enqueue_jurisdictions_sheet_sync() -> None:
    """Refresh the dropdown source. One at a time — the id carries no argument because the tab
    covers every state, so a second request while one runs is genuinely the same work."""
    client = await _get_client()
    await client.start_workflow(
        JurisdictionsSheetSyncWorkflow.run,
        id="jurisdictions-sheet-sync",
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
    selection = ",".join(
        sorted(cid for item in request.items for cid in item.changeset_ids)
    )
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
