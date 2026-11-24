"""One collector run (pipelines 1 and 2), on Temporal's time-skipping test server with stub
activities registered under the real names. Every activity receives the kind first, so one
workflow serves every collector. A state's pass is `test_collector_state_workflow`."""

import uuid

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from lib.temporal.collector_workflows import CollectorWorkflow
from lib.temporal.types import RunConclusion
from shared.utils.statuses import PipelineRunKind, PipelineRunStatus

pytestmark = pytest.mark.unit

_KIND = PipelineRunKind.GOVERNING_LAW_COLLECTOR.value


class Recorder:
    def __init__(self, conclusion: str = RunConclusion.SUCCESS, trigger_fails: bool = False):
        self.conclusion = conclusion
        self.trigger_fails = trigger_fails
        self.kinds: set[str] = set()
        self.local: list[str] = []
        self.remote: list[str] = []
        self.statuses: list[str] = []
        self.cancelled: list[str] = []


def _activities(rec: Recorder):
    @activity.defn(name="trigger_collector_local")
    async def trigger_local(kind, jurisdiction_ocdid, pipeline_run_id):
        rec.kinds.add(kind)
        if rec.trigger_fails:
            raise RuntimeError("pipelines server unreachable")
        rec.local.append(pipeline_run_id)

    @activity.defn(name="trigger_collector_remote")
    async def trigger_remote(kind, jurisdiction_ocdid, pipeline_run_id):
        rec.kinds.add(kind)
        rec.remote.append(pipeline_run_id)

    @activity.defn(name="poll_pipeline_run_status")
    async def poll(pipeline_run_id):
        return rec.conclusion

    @activity.defn(name="update_pipeline_run_status")
    async def update_status(pipeline_run_id, status, progress=None):
        rec.statuses.append(status)

    @activity.defn(name="cancel_local_pipeline_run")
    async def cancel_local_pipeline_run(pipeline_run_id):
        rec.cancelled.append(pipeline_run_id)

    return [trigger_local, trigger_remote, poll, update_status, cancel_local_pipeline_run]


async def _execute(rec: Recorder, workflow_run, args: list):
    async with await WorkflowEnvironment.start_time_skipping() as env:
        queue = f"test-{uuid.uuid4()}"
        async with Worker(env.client, task_queue=queue, workflows=[CollectorWorkflow], activities=_activities(rec)):
            return await env.client.execute_workflow(workflow_run, args=args, id=f"t-{uuid.uuid4()}", task_queue=queue)


_OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"


@pytest.mark.asyncio
async def test_a_run_is_dispatched_through_its_kinds_door_and_settled():
    rec = Recorder()

    conclusion = await _execute(rec, CollectorWorkflow.run, [_KIND, _OCDID, "run-1", "local"])

    assert conclusion == RunConclusion.SUCCESS
    assert rec.local == ["run-1"] and rec.remote == []
    assert rec.kinds == {_KIND}
    assert rec.statuses == [PipelineRunStatus.RUNNING, PipelineRunStatus.SUCCESS]


@pytest.mark.asyncio
async def test_a_remote_run_goes_through_the_actions_workflow():
    rec = Recorder()

    await _execute(rec, CollectorWorkflow.run, [_KIND, _OCDID, "run-1", "remote"])

    assert rec.remote == ["run-1"] and rec.local == []


@pytest.mark.asyncio
async def test_a_run_that_cannot_be_dispatched_is_settled_as_an_error_and_stopped():
    rec = Recorder(trigger_fails=True)

    with pytest.raises(WorkflowFailureError):
        await _execute(rec, CollectorWorkflow.run, [_KIND, _OCDID, "run-1", "local"])

    assert rec.statuses[-1] == PipelineRunStatus.ERROR
    assert rec.cancelled == ["run-1"]
