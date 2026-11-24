"""One jurisdiction's scrape run, on Temporal's time-skipping test server with stub activities
registered under the real names. A state's pass is `test_collector_state_workflow`."""

import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from lib.temporal.pipeline_run_workflows import PeopleCollectorWorkflow
from shared.utils.statuses import PipelineRunStatus

pytestmark = pytest.mark.unit


def _activities_that_stop_watching(reported: list[tuple[str, str]]):
    """`poll_pipeline_run_status` fails the way it does when GitHub has killed the job: the run
    never reports an ending, so the poller times out rather than returning a conclusion."""

    @activity.defn(name="trigger_people_collector_remote")
    async def trigger_people_collector_remote(jurisdiction_ocdid, pipeline_run_id, url=None, source_urls=None):
        return None

    @activity.defn(name="trigger_people_collector_local")
    async def trigger_people_collector_local(jurisdiction_ocdid, pipeline_run_id, url=None, source_urls=None):
        return None

    @activity.defn(name="poll_pipeline_run_status")
    async def poll_pipeline_run_status(pipeline_run_id: str):
        raise RuntimeError("stopped watching")

    @activity.defn(name="update_pipeline_run_status")
    async def update_pipeline_run_status(
        pipeline_run_id, status, progress=None, error_type=None, error_detail=None
    ):
        reported.append((pipeline_run_id, status, error_type))

    @activity.defn(name="cancel_local_pipeline_run")
    async def cancel_local_pipeline_run(pipeline_run_id: str):
        return None

    return [
        trigger_people_collector_remote,
        trigger_people_collector_local,
        poll_pipeline_run_status,
        update_pipeline_run_status,
        cancel_local_pipeline_run,
    ]


@pytest.mark.asyncio
async def test_a_run_whose_watcher_gives_up_is_settled_rather_than_left_running():
    """Otherwise only `expire_stale_pipeline_runs` closes it — six hours later, with the
    jurisdiction blocked from re-scraping the whole time."""
    reported: list[tuple[str, str, str | None]] = []
    run_id = str(uuid.uuid4())

    async with await WorkflowEnvironment.start_time_skipping() as env:
        queue = f"test-{uuid.uuid4()}"
        async with Worker(
            env.client,
            task_queue=queue,
            workflows=[PeopleCollectorWorkflow],
            activities=_activities_that_stop_watching(reported),
        ):
            with pytest.raises(Exception):
                await env.client.execute_workflow(
                    PeopleCollectorWorkflow.run,
                    args=["ocd-jurisdiction/country:us/state:zz/place:p/government", run_id, "remote", None, None],
                    id=f"people-collector-{uuid.uuid4()}",
                    task_queue=queue,
                )

    assert (run_id, PipelineRunStatus.ERROR, "pipeline_error") in reported, (
        f"the run was left unsettled, or settled without an issue to read; reports were {reported}"
    )
