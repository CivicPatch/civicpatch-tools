"""The state scrape's claim-per-slice loop, run for real against Temporal's time-skipping
test server.

This is the layer that matters here: the loop's whole job is *when it stops*, and the three
termination conditions are a property of the sequence of activity results, not of any one call.
Nothing below is mocked in the usual sense — the workflow really runs, really dispatches child
workflows, and the activities are stub implementations registered under the real names.
"""

import asyncio
import uuid

import pytest
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from core.spend_limits import Cap
from lib.temporal.pipeline_run_workflows import (
    PeopleCollectorWorkflow,
    PeopleCollectorStateWorkflow,
)
from lib.temporal.types import RunConclusion
from shared.utils.statuses import PipelineRunStatus

pytestmark = pytest.mark.unit


class Recorder:
    """What the loop asked for, in order. `claims` is the interesting one: its length is how
    many times the loop went round, and its values are the slice sizes it requested."""

    def __init__(self, pool: int, cap_after: int | None = None, quiet_runs: int = 0):
        self.pool = pool  # jurisdictions still unclaimed in the state
        self.cap_after = cap_after  # trip the budget after this many claims
        self.quiet_runs = quiet_runs  # the first this many watches give up
        self.total = pool
        self.hold_first_run = False
        self.others_started_while_held = False
        self.claims: list[int] = []
        self.dispatched: list[str] = []
        self.dispatched_locally: list[str] = []


async def _until(condition, attempts: int = 200) -> bool:
    for _ in range(attempts):
        if condition():
            return True
        await asyncio.sleep(0.01)
    return False


async def _watch(rec: Recorder) -> str:
    if rec.quiet_runs > 0:
        rec.quiet_runs -= 1
        raise ApplicationError("reported nothing new", non_retryable=True)
    if rec.hold_first_run:
        rec.hold_first_run = False
        rec.others_started_while_held = await _until(lambda: len(rec.dispatched) == rec.total)
    return RunConclusion.SUCCESS


def _activities(rec: Recorder):
    @activity.defn(name="people_collector_month_cap_reached")
    async def people_collector_month_cap_reached(state: str):
        if rec.cap_after is not None and len(rec.claims) >= rec.cap_after:
            return Cap.STATE_MONTH.value
        return None

    @activity.defn(name="claim_jurisdictions_for_people_collector")
    async def claim_jurisdictions_for_people_collector(state, num_jurisdictions=None, created_by_user_id=None):
        rec.claims.append(num_jurisdictions)
        take = min(num_jurisdictions or rec.pool, rec.pool)
        rec.pool -= take
        # The claim registers a run for what it hands back, so it never returns the same
        # jurisdiction twice — that is what makes the loop terminate.
        return [
            {
                "jurisdiction_ocdid": f"ocd-jurisdiction/country:us/state:{state}/place:p{uuid.uuid4().hex[:8]}/government",
                "pipeline_run_id": str(uuid.uuid4()),
            }
            for _ in range(take)
        ]

    @activity.defn(name="trigger_people_collector_remote")
    async def trigger_people_collector_remote(jurisdiction_ocdid, pipeline_run_id, url=None, source_urls=None):
        rec.dispatched.append(jurisdiction_ocdid)

    @activity.defn(name="trigger_people_collector_local")
    async def trigger_people_collector_local(jurisdiction_ocdid, pipeline_run_id, url=None, source_urls=None):
        rec.dispatched.append(jurisdiction_ocdid)
        rec.dispatched_locally.append(jurisdiction_ocdid)

    @activity.defn(name="poll_pipeline_run_status")
    async def poll_pipeline_run_status(pipeline_run_id: str):
        return await _watch(rec)

    @activity.defn(name="update_pipeline_run_status")
    async def update_pipeline_run_status(pipeline_run_id, status, progress=None, error_type=None, error_detail=None):
        return None

    @activity.defn(name="cancel_local_pipeline_run")
    async def cancel_local_pipeline_run(pipeline_run_id: str):
        return None

    return [
        people_collector_month_cap_reached,
        claim_jurisdictions_for_people_collector,
        trigger_people_collector_remote,
        trigger_people_collector_local,
        poll_pipeline_run_status,
        update_pipeline_run_status,
        cancel_local_pipeline_run,
    ]


async def _run_state_scrape(rec: Recorder, **kwargs) -> int:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        queue = f"test-{uuid.uuid4()}"
        async with Worker(
            env.client,
            task_queue=queue,
            workflows=[PeopleCollectorStateWorkflow, PeopleCollectorWorkflow],
            activities=_activities(rec),
        ):
            return await env.client.execute_workflow(
                PeopleCollectorStateWorkflow.run,
                args=[
                    kwargs.get("state", "zz"),
                    kwargs.get("num_jurisdictions"),
                    None,
                    kwargs.get("concurrency", 5),
                    kwargs.get("dispatch_mode", "remote"),
                ],
                id=f"people-collector-state-{uuid.uuid4()}",
                task_queue=queue,
            )


@pytest.mark.asyncio
async def test_it_claims_one_place_per_run_it_starts():
    """Only what is started is ever claimed, so stopping leaves nothing registered-but-unstarted
    to freeze a jurisdiction out of the pool."""
    rec = Recorder(pool=12)

    dispatched = await _run_state_scrape(rec, concurrency=5)

    assert set(rec.claims) == {1}
    assert dispatched == 12


@pytest.mark.asyncio
async def test_a_local_state_scrape_dispatches_every_child_locally():
    rec = Recorder(pool=3)

    await _run_state_scrape(rec, concurrency=5, dispatch_mode="local")

    assert len(rec.dispatched_locally) == 3


@pytest.mark.asyncio
async def test_it_stops_when_the_state_runs_out_of_candidates():
    """The claim returning nothing is the ordinary end of a state scrape."""
    rec = Recorder(pool=3)

    dispatched = await _run_state_scrape(rec, concurrency=5)

    assert dispatched == 3
    assert rec.claims == [1, 1, 1, 1]  # three places, then asked again and got nothing


@pytest.mark.asyncio
async def test_it_stops_at_the_budget_and_reports_what_it_dispatched():
    """Not what it claimed — the honest number when a scrape halts early. And nothing is
    claimed after the cap is reached, which is what makes the release unnecessary."""
    rec = Recorder(pool=100, cap_after=2)

    dispatched = await _run_state_scrape(rec, concurrency=5)

    assert len(rec.claims) == 2
    assert dispatched == sum(rec.claims)


@pytest.mark.asyncio
async def test_a_state_already_over_budget_dispatches_nothing():
    """The gate is checked before the first claim, so a `$0` monthly cap is a stop switch and
    not merely a brake."""
    rec = Recorder(pool=100, cap_after=0)

    dispatched = await _run_state_scrape(rec, concurrency=5)

    assert rec.claims == []
    assert dispatched == 0


@pytest.mark.asyncio
async def test_it_never_claims_more_than_the_caller_asked_for():
    """`num_jurisdictions` is a request for that many, not that many per slice."""
    rec = Recorder(pool=100)

    dispatched = await _run_state_scrape(rec, concurrency=5, num_jurisdictions=7)

    assert rec.claims == [1] * 7
    assert dispatched == 7


@pytest.mark.asyncio
async def test_a_run_that_fails_does_not_end_the_state_scrape():
    rec = Recorder(pool=12, quiet_runs=1)

    dispatched = await _run_state_scrape(rec, concurrency=5)

    assert dispatched == 12


@pytest.mark.asyncio
async def test_a_slow_run_does_not_hold_up_the_rest():
    rec = Recorder(pool=12)
    rec.hold_first_run = True

    dispatched = await _run_state_scrape(rec, concurrency=5)

    assert rec.others_started_while_held
    assert dispatched == 12


# --- a run whose watcher gives up -------------------------------------------------------


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
