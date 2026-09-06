"""The four workers, and the traps that come with splitting one into four.

`pr-sync` failed a workflow task 1139 times over a week after its class was removed: retiring the
schedule stopped new firings, but the execution it had already started stayed open forever. The
startup sweep closes those, and must stay scoped to one task queue — the other workers share the
namespace and legitimately run workflows this one has never heard of.

Was `test_worker.py`, when there was one worker.
"""

import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest

import lib.temporal.schedules as schedules
from lib.temporal.types import (
    EXPIRY_TASK_QUEUE,
    SCRAPE_TASK_QUEUE,
    SINKS_TASK_QUEUE,
    JURISDICTIONS_TASK_QUEUE,
)

# worker module -> (its queue, the activities module it should register in full)
WORKERS = {
    "workers.jurisdictions": (JURISDICTIONS_TASK_QUEUE, "routers.temporal.jurisdiction_activities"),
    "workers.sinks": (SINKS_TASK_QUEUE, "routers.temporal.sink_activities"),
    "workers.expiry": (EXPIRY_TASK_QUEUE, "routers.temporal.expiry_activities"),
    "workers.scrape": (SCRAPE_TASK_QUEUE, "routers.temporal.scrape_activities"),
}


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

    await schedules.terminate_undeclared_workflows(
        client, JURISDICTIONS_TASK_QUEUE, {"OdSyncWorkflow"}
    )

    handle.terminate.assert_awaited_once()
    assert client.get_workflow_handle.call_args.args == (
        "pr-sync-workflow-2026-08-25T22:00:00Z",
    )


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("task_queue", sorted({q for q, _ in WORKERS.values()}))
async def test_sweep_is_scoped_to_one_task_queue(task_queue):
    """Namespace-wide, this would terminate the other three workers' running executions."""
    client = MagicMock()
    client.list_workflows = MagicMock(return_value=_executions())

    await schedules.terminate_undeclared_workflows(client, task_queue, set())

    assert f"TaskQueue='{task_queue}'" in client.list_workflows.call_args.args[0]


@pytest.mark.unit
@pytest.mark.parametrize("module_name", sorted(WORKERS))
def test_registered_workflow_names_match_the_temporal_type_names(module_name):
    """The sweep compares Temporal's `workflow_type` against class names, and `schedules.py`
    names workflows by string — so a `@workflow.defn(name=...)` override would both make every
    workflow look undeclared and point the schedules at nothing."""
    module = importlib.import_module(module_name)
    for workflow in module.WORKFLOWS:
        assert workflow.__temporal_workflow_definition.name == workflow.__name__


@pytest.mark.unit
def test_every_schedule_points_at_a_workflow_the_queue_actually_registers():
    """The trap the split introduces. A schedule carries a workflow *name* and a task queue,
    neither typechecked. Name a workflow that no worker on that queue registers and the schedule
    fires into nothing — the failure is a workflow task retrying forever, which is exactly the
    `pr-sync` shape.

    This replaces the old "two-place trap" test: `register_schedules` now derives its declared
    set from `_SCHEDULES` directly, so a schedule can no longer be created without being
    declared.
    """
    registered: dict[str, set[str]] = {}
    for module_name, (task_queue, _) in WORKERS.items():
        module = importlib.import_module(module_name)
        registered.setdefault(task_queue, set()).update(
            workflow.__name__ for workflow in module.WORKFLOWS
        )

    assert schedules._SCHEDULES, "no schedules declared — introspection broke"
    for schedule_id, (workflow_name, _, task_queue, _cron) in schedules._SCHEDULES.items():
        assert workflow_name in registered.get(task_queue, set()), (
            f"schedule {schedule_id} starts {workflow_name} on {task_queue}, "
            f"which registers {sorted(registered.get(task_queue, set()))}"
        )


@pytest.mark.unit
@pytest.mark.parametrize("module_name", sorted(WORKERS))
def test_every_activity_defined_is_registered_on_the_worker(module_name):
    """The sibling trap, and it bit during the daily-sweep work: an activity can be imported
    into a worker and still be missing from `activities=[...]`, which typechecks fine and fails
    at runtime with "activity is not registered" — but only when the schedule that needs it
    fires, which for a daily workflow is up to a day later.

    Over-inclusive on purpose. An activity nobody calls yet still costs nothing to register,
    where a called one that is missing costs a silent dead schedule.
    """
    worker = importlib.import_module(module_name)
    activities_module = importlib.import_module(WORKERS[module_name][1])

    defined = {
        name
        for name, value in vars(activities_module).items()
        if callable(value) and hasattr(value, "__temporal_activity_definition")
    }
    registered = {a.__name__ for a in worker.ACTIVITIES}

    assert defined, "no activities found — the introspection broke, not the registration"
    assert defined - registered == set()
