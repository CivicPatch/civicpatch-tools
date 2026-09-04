"""A deleted workflow class leaves its already-running executions behind.

`pr-sync` failed a workflow task 1139 times over a week after its class was removed: retiring the
schedule stopped new firings, but the execution it had already started stayed open forever. The
startup sweep closes those. It must stay scoped to this worker's task queue — the pipelines
worker shares the namespace and legitimately runs workflows this one has never heard of.
"""

from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_every_schedule_it_creates_is_one_it_declares():
    """The two-place trap. A schedule is registered in `_register_schedules` and named again in
    the set passed to `_retire_undeclared_schedules`; miss the second and the worker deletes on
    its next boot the schedule it just created, silently, every time it starts.

    Asserted by running the real function, so adding a sixth schedule and forgetting the set
    fails here rather than in a log line nobody reads.
    """
    created: list[str] = []
    declared: set[str] = set()

    async def _record_create(_client, schedule_id, _schedule):
        created.append(schedule_id)

    async def _record_declare(_client, ids):
        declared.update(ids)

    with (
        patch.object(worker, "_ensure_schedule", _record_create),
        patch.object(worker, "_retire_undeclared_schedules", _record_declare),
    ):
        await worker._register_schedules(AsyncMock())

    assert created, "the worker should register at least one schedule"
    assert set(created) == declared


@pytest.mark.unit
def test_every_activity_defined_is_registered_on_the_worker():
    """The sibling of the schedule trap, and it bit during the daily-sweep work: an activity
    can be imported into `worker.py` and still be missing from `activities=[...]`, which
    typechecks fine and fails at runtime with "activity is not registered" — but only when the
    schedule that needs it fires, which for a daily workflow is up to a day later.

    Over-inclusive on purpose. An activity nobody calls yet still costs nothing to register,
    where a called one that is missing costs a silent dead schedule.
    """
    import routers.temporal.activities as activities_module

    defined = {
        name
        for name, value in vars(activities_module).items()
        if callable(value) and hasattr(value, "__temporal_activity_definition")
    }
    registered = {a.__name__ for a in worker.ACTIVITIES}

    assert defined, "no activities found — the introspection broke, not the registration"
    assert defined - registered == set()
