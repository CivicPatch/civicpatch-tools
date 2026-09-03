"""A deleted workflow class leaves its already-running executions behind.

`pr-sync` failed a workflow task 1139 times over a week after its class was removed: retiring the
schedule stopped new firings, but the execution it had already started stayed open forever. The
startup sweep closes those. It must stay scoped to this worker's task queue — the pipelines
worker shares the namespace and legitimately runs workflows this one has never heard of.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import worker
from lib.temporal.workflows import TASK_QUEUE


def _execution(workflow_id: str, workflow_type: str) -> MagicMock:
    execution = MagicMock()
    execution.id = workflow_id
    execution.run_id = f"run-{workflow_id}"
    execution.workflow_type = workflow_type
    return execution


async def _executions(*items):
    for item in items:
        yield item


@pytest.mark.unit
@pytest.mark.asyncio
async def test_terminates_only_the_workflows_this_worker_no_longer_registers():
    handle = MagicMock()
    handle.terminate = AsyncMock()
    client = MagicMock()
    client.list_workflows = MagicMock(
        return_value=_executions(
            _execution("od-sync", "OdSyncWorkflow"),
            _execution("pr-sync-workflow-2026-08-25T22:00:00Z", "PRSyncWorkflow"),
        )
    )
    client.get_workflow_handle = MagicMock(return_value=handle)

    await worker._terminate_undeclared_workflows(client, {"OdSyncWorkflow"})

    handle.terminate.assert_awaited_once()
    assert client.get_workflow_handle.call_args.args == (
        "pr-sync-workflow-2026-08-25T22:00:00Z",
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sweep_is_scoped_to_this_workers_task_queue():
    """Namespace-wide, this would terminate the pipelines worker's running scrapes."""
    client = MagicMock()
    client.list_workflows = MagicMock(return_value=_executions())

    await worker._terminate_undeclared_workflows(client, set())

    assert f"TaskQueue='{TASK_QUEUE}'" in client.list_workflows.call_args.args[0]


@pytest.mark.unit
def test_registered_workflow_names_match_the_temporal_type_names():
    """The sweep compares Temporal's `workflow_type` against class names, so a
    `@workflow.defn(name=...)` override would silently make every workflow look undeclared."""
    for workflow in worker.WORKFLOWS:
        assert workflow.__temporal_workflow_definition.name == workflow.__name__
