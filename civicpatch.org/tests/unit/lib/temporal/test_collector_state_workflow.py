"""A state's pass, for every pipeline, run for real on Temporal's time-skipping test server.

The loop's whole job is when it claims and when it stops, which is a property of the sequence of
activity results, not of any one call. The workflows really run and really start their children;
the activities are stubs registered under the real names, both the scrape's and the collectors'.
"""

import asyncio
import uuid

import pytest
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from core.spend_limits import Cap
from lib.temporal.collector_workflows import CollectorStateWorkflow, CollectorWorkflow
from lib.temporal.pipeline_run_workflows import PeopleCollectorWorkflow
from lib.temporal.types import RunConclusion
from shared.utils.statuses import PipelineRunKind

pytestmark = pytest.mark.unit

KINDS = [kind.value for kind in PipelineRunKind]


class Recorder:
    """What the pass asked for, in order. `claims` holds the count each claim asked for."""

    def __init__(self, pool: int, cap_after: int | None = None, quiet_runs: int = 0):
        self.pool = pool  # jurisdictions still unclaimed in the state
        self.total = pool
        self.cap_after = cap_after  # the budget trips after this many claims
        self.quiet_runs = quiet_runs  # the first this many watches give up
        self.hold_first_run = False
        self.others_started_while_held = False
        self.claims: list[int] = []
        self.dispatched: list[str] = []
        self.dispatched_locally: list[str] = []


def _cap(rec: Recorder) -> str | None:
    if rec.cap_after is not None and len(rec.claims) >= rec.cap_after:
        return Cap.STATE_MONTH.value
    return None


def _claim(rec: Recorder, state: str, num_jurisdictions: int) -> list[dict]:
    rec.claims.append(num_jurisdictions)
    take = min(num_jurisdictions, rec.pool)
    rec.pool -= take
    # The claim registers a run for what it hands back, so it never returns the same place twice.
    return [
        {
            "jurisdiction_ocdid": f"ocd-jurisdiction/country:us/state:{state}/place:p{uuid.uuid4().hex[:8]}/government",
            "pipeline_run_id": str(uuid.uuid4()),
        }
        for _ in range(take)
    ]


def _trigger(rec: Recorder, jurisdiction_ocdid: str, locally: bool) -> None:
    rec.dispatched.append(jurisdiction_ocdid)
    if locally:
        rec.dispatched_locally.append(jurisdiction_ocdid)


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


def _scrape_activities(rec: Recorder) -> list:
    @activity.defn(name="people_collector_month_cap_reached")
    async def people_collector_month_cap_reached(state):
        return _cap(rec)

    @activity.defn(name="claim_jurisdictions_for_people_collector")
    async def claim_jurisdictions_for_people_collector(state, num_jurisdictions=None, created_by_user_id=None):
        return _claim(rec, state, num_jurisdictions)

    @activity.defn(name="trigger_people_collector_remote")
    async def trigger_people_collector_remote(jurisdiction_ocdid, pipeline_run_id, url=None, source_urls=None):
        _trigger(rec, jurisdiction_ocdid, locally=False)

    @activity.defn(name="trigger_people_collector_local")
    async def trigger_people_collector_local(jurisdiction_ocdid, pipeline_run_id, url=None, source_urls=None):
        _trigger(rec, jurisdiction_ocdid, locally=True)

    return [
        people_collector_month_cap_reached,
        claim_jurisdictions_for_people_collector,
        trigger_people_collector_remote,
        trigger_people_collector_local,
    ]


def _collector_activities(rec: Recorder) -> list:
    @activity.defn(name="collector_month_cap_reached")
    async def collector_month_cap_reached(kind, state):
        return _cap(rec)

    @activity.defn(name="claim_jurisdictions_for_collector")
    async def claim_jurisdictions_for_collector(kind, state, num_jurisdictions, created_by_user_id, state_batch_id):
        return _claim(rec, state, num_jurisdictions)

    @activity.defn(name="trigger_collector_remote")
    async def trigger_collector_remote(kind, jurisdiction_ocdid, pipeline_run_id):
        _trigger(rec, jurisdiction_ocdid, locally=False)

    @activity.defn(name="trigger_collector_local")
    async def trigger_collector_local(kind, jurisdiction_ocdid, pipeline_run_id):
        _trigger(rec, jurisdiction_ocdid, locally=True)

    return [
        collector_month_cap_reached,
        claim_jurisdictions_for_collector,
        trigger_collector_remote,
        trigger_collector_local,
    ]


def _shared_activities(rec: Recorder) -> list:
    @activity.defn(name="poll_pipeline_run_status")
    async def poll_pipeline_run_status(pipeline_run_id: str):
        return await _watch(rec)

    @activity.defn(name="update_pipeline_run_status")
    async def update_pipeline_run_status(pipeline_run_id, status, progress=None, error_type=None, error_detail=None):
        return None

    @activity.defn(name="cancel_local_pipeline_run")
    async def cancel_local_pipeline_run(pipeline_run_id: str):
        return None

    return [poll_pipeline_run_status, update_pipeline_run_status, cancel_local_pipeline_run]


async def _run_pass(rec: Recorder, kind: str, num_jurisdictions: int | None = None, dispatch_mode: str = "remote") -> int:
    activities = _scrape_activities(rec) + _collector_activities(rec) + _shared_activities(rec)
    async with await WorkflowEnvironment.start_time_skipping() as env:
        queue = f"test-{uuid.uuid4()}"
        async with Worker(
            env.client,
            task_queue=queue,
            workflows=[CollectorStateWorkflow, CollectorWorkflow, PeopleCollectorWorkflow],
            activities=activities,
        ):
            return await env.client.execute_workflow(
                CollectorStateWorkflow.run,
                args=[kind, "zz", num_jurisdictions, None, 5, dispatch_mode],
                id=f"collector-state-{uuid.uuid4()}",
                task_queue=queue,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_it_claims_one_place_per_run_it_starts(kind):
    """Only what is started is ever claimed, so stopping leaves nothing registered-but-unstarted
    to freeze a jurisdiction out of the pool."""
    rec = Recorder(pool=12)

    dispatched = await _run_pass(rec, kind)

    assert set(rec.claims) == {1}
    assert dispatched == 12
    assert len(rec.dispatched) == 12


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_a_local_pass_dispatches_every_child_locally(kind):
    rec = Recorder(pool=3)

    await _run_pass(rec, kind, dispatch_mode="local")

    assert len(rec.dispatched_locally) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_it_stops_when_the_state_runs_out_of_candidates(kind):
    """The claim returning nothing is the ordinary end of a pass."""
    rec = Recorder(pool=3)

    dispatched = await _run_pass(rec, kind)

    assert dispatched == 3
    assert rec.claims == [1, 1, 1, 1]  # three places, then asked again and got nothing


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_it_stops_at_the_budget_and_reports_what_it_dispatched(kind):
    """Nothing is claimed after the cap is reached, which is what makes a release unnecessary."""
    rec = Recorder(pool=100, cap_after=2)

    dispatched = await _run_pass(rec, kind)

    assert len(rec.claims) == 2
    assert dispatched == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_a_state_already_over_budget_dispatches_nothing(kind):
    """The gate is checked before the first claim, so a `$0` monthly cap is a stop switch."""
    rec = Recorder(pool=100, cap_after=0)

    dispatched = await _run_pass(rec, kind)

    assert rec.claims == []
    assert dispatched == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_it_never_claims_more_than_the_caller_asked_for(kind):
    """`num_jurisdictions` is a request for that many in all."""
    rec = Recorder(pool=100)

    dispatched = await _run_pass(rec, kind, num_jurisdictions=7)

    assert rec.claims == [1] * 7
    assert dispatched == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_a_run_that_fails_does_not_end_the_pass(kind):
    rec = Recorder(pool=12, quiet_runs=1)

    dispatched = await _run_pass(rec, kind)

    assert dispatched == 12


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_a_slow_run_does_not_hold_up_the_rest(kind):
    rec = Recorder(pool=12)
    rec.hold_first_run = True

    dispatched = await _run_pass(rec, kind)

    assert rec.others_started_while_held
    assert dispatched == 12
