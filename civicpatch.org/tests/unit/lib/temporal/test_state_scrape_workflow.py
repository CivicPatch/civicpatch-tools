"""The state scrape's claim-per-slice loop, run for real against Temporal's time-skipping
test server.

This is the layer that matters here: the loop's whole job is *when it stops*, and the three
termination conditions are a property of the sequence of activity results, not of any one call.
Nothing below is mocked in the usual sense — the workflow really runs, really dispatches child
workflows, and the activities are stub implementations registered under the real names.
"""

import uuid

import pytest
from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from core.spend_limits import Cap
from lib.temporal.scrape_workflows import (
    BatchPeopleCollectorWorkflow,
    PeopleCollectorWorkflow,
    StateScrapeWorkflow,
)
from lib.temporal.types import RunConclusion
from shared.utils.statuses import PipelineRunStatus

pytestmark = pytest.mark.unit


class Recorder:
    """What the loop asked for, in order. `claims` is the interesting one: its length is how
    many times the loop went round, and its values are the slice sizes it requested."""

    def __init__(self, pool: int, cap_after: int | None = None):
        self.pool = pool  # jurisdictions still unclaimed in the state
        self.cap_after = cap_after  # trip the budget after this many claims
        self.claims: list[int] = []
        self.dispatched: list[str] = []


def _activities(rec: Recorder):
    @activity.defn(name="budget_cap_reached")
    async def budget_cap_reached(state: str):
        if rec.cap_after is not None and len(rec.claims) >= rec.cap_after:
            return Cap.STATE_MONTH.value
        return None

    @activity.defn(name="claim_scrape_candidates")
    async def claim_scrape_candidates(state, num_jurisdictions=None, created_by_user_id=None):
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

    @activity.defn(name="trigger_github_action")
    async def trigger_github_action(jurisdiction_ocdid, pipeline_run_id, url=None, source_urls=None):
        rec.dispatched.append(jurisdiction_ocdid)

    @activity.defn(name="trigger_local")
    async def trigger_local(jurisdiction_ocdid, pipeline_run_id, url=None, source_urls=None):
        rec.dispatched.append(jurisdiction_ocdid)

    @activity.defn(name="poll_pipeline_run_status")
    async def poll_pipeline_run_status(pipeline_run_id: str):
        return RunConclusion.SUCCESS

    @activity.defn(name="update_pipeline_run_status")
    async def update_pipeline_run_status(pipeline_run_id, status, progress=None):
        return None

    @activity.defn(name="cancel_local_run")
    async def cancel_local_run(pipeline_run_id: str):
        return None

    return [
        budget_cap_reached,
        claim_scrape_candidates,
        trigger_github_action,
        trigger_local,
        poll_pipeline_run_status,
        update_pipeline_run_status,
        cancel_local_run,
    ]


async def _run_state_scrape(rec: Recorder, **kwargs) -> int:
    async with await WorkflowEnvironment.start_time_skipping() as env:
        queue = f"test-{uuid.uuid4()}"
        async with Worker(
            env.client,
            task_queue=queue,
            workflows=[StateScrapeWorkflow, PeopleCollectorWorkflow, BatchPeopleCollectorWorkflow],
            activities=_activities(rec),
        ):
            return await env.client.execute_workflow(
                StateScrapeWorkflow.run,
                args=[kwargs.get("state", "zz"), kwargs.get("num_jurisdictions"), None, kwargs.get("concurrency", 5)],
                id=f"state-scrape-{uuid.uuid4()}",
                task_queue=queue,
            )


@pytest.mark.asyncio
async def test_it_claims_a_slice_at_a_time_rather_than_the_whole_state():
    """The point of the redesign: only the slice in flight is ever claimed, so stopping leaves
    nothing registered-but-unstarted to freeze a jurisdiction out of the pool."""
    rec = Recorder(pool=12)

    dispatched = await _run_state_scrape(rec, concurrency=5)

    # Four claims for twelve jurisdictions at a slice of five: 5, 5, 2, then one more that
    # comes back empty. That last empty claim IS the termination condition — the loop has no
    # count to compare against, so it learns the state is drained by asking.
    assert rec.claims == [5, 5, 5, 5]
    assert dispatched == 12


@pytest.mark.asyncio
async def test_it_stops_when_the_state_runs_out_of_candidates():
    """The claim returning nothing is the ordinary end of a state scrape."""
    rec = Recorder(pool=3)

    dispatched = await _run_state_scrape(rec, concurrency=5)

    assert dispatched == 3
    assert rec.claims == [5, 5]  # got the remainder, then asked again and got nothing


@pytest.mark.asyncio
async def test_it_stops_at_the_budget_and_reports_what_it_dispatched():
    """Not what it claimed — the honest number when a scrape halts early. And nothing is
    claimed after the cap is reached, which is what makes the release unnecessary."""
    rec = Recorder(pool=100, cap_after=2)

    dispatched = await _run_state_scrape(rec, concurrency=5)

    assert len(rec.claims) == 2
    assert dispatched == 10


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

    assert rec.claims == [5, 2]
    assert dispatched == 7
