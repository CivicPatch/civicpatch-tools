"""GenerateMapsWorkflow run for real against Temporal's time-skipping test server.

Nothing below is mocked in the usual sense — the workflow really runs, and the activities
are stub implementations registered under the real names.
"""

import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from lib.temporal.map_generation_workflows import GenerateMapsWorkflow

pytestmark = pytest.mark.unit


class Recorder:
    def __init__(self):
        self.calls: list[str] = []


def _activities(rec: Recorder, *, state_fails: bool = False):
    @activity.defn(name="build_and_upload_state_pmtiles")
    async def build_and_upload_state_pmtiles(state: str):
        rec.calls.append(f"state:{state}")
        if state_fails:
            raise RuntimeError("TIGER download failed")
        return f"https://cdn.example.com/maps/{state}.pmtiles"

    @activity.defn(name="build_and_upload_national_overview")
    async def build_and_upload_national_overview():
        rec.calls.append("national")
        return "https://cdn.example.com/maps/states.pmtiles"

    return [build_and_upload_state_pmtiles, build_and_upload_national_overview]


async def _run_workflow(rec: Recorder, state: str = "co", **kwargs):
    async with await WorkflowEnvironment.start_time_skipping() as env:
        queue = f"test-{uuid.uuid4()}"
        async with Worker(
            env.client,
            task_queue=queue,
            workflows=[GenerateMapsWorkflow],
            activities=_activities(rec, **kwargs),
        ):
            return await env.client.execute_workflow(
                GenerateMapsWorkflow.run,
                args=[state],
                id=f"generate-maps-{uuid.uuid4()}",
                task_queue=queue,
            )


@pytest.mark.asyncio
async def test_builds_the_state_then_refreshes_the_national_overview():
    rec = Recorder()

    url = await _run_workflow(rec, state="co")

    assert rec.calls == ["state:co", "national"]
    assert url == "https://cdn.example.com/maps/co.pmtiles"


@pytest.mark.asyncio
async def test_national_overview_is_skipped_when_the_state_build_fails():
    """Nothing new to reflect in the picker if the state itself never built."""
    rec = Recorder()

    with pytest.raises(Exception):
        await _run_workflow(rec, state="co", state_fails=True)

    # retry_policy allows 2 attempts at the state activity before the workflow gives up.
    assert rec.calls == ["state:co", "state:co"]
