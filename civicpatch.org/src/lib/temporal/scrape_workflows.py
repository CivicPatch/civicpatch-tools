"""The scrape workflows: one jurisdiction, and a whole state's worth of them.

Moved from the standalone `worker` package on 2026-09-05. They run on their own task queue,
registered by `workers/scrape.py`, its own process and pod — a different
concurrency budget, because these activities are thin and long-lived where the sync ones are
short and memory-hungry.
"""

import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from lib.temporal.types import RunConclusion
    from routers.temporal.scrape_activities import (
        cancel_local_run,
        budget_cap_reached,
        claim_scrape_candidates,
        poll_pipeline_run_status,
        trigger_github_action,
        trigger_local,
        update_pipeline_run_status,
    )
    from shared.utils.statuses import PipelineRunStatus

_DISPATCH_MODE_LOCAL = "local"


def _workflow_id(jurisdiction_ocdid: str) -> str:
    safe = jurisdiction_ocdid.replace("/", "-").replace(":", "-")
    return f"people-collector-{safe}"


@workflow.defn
class PeopleCollectorWorkflow:
    @workflow.run
    async def run(
        self,
        jurisdiction_ocdid: str,
        pipeline_run_id: str,
        dispatch_mode: str = "remote",
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        await workflow.execute_activity(
            update_pipeline_run_status,
            args=[pipeline_run_id, PipelineRunStatus.RUNNING],
            start_to_close_timeout=timedelta(seconds=30),
        )
        try:
            conclusion = await self._dispatch_and_poll(dispatch_mode, jurisdiction_ocdid, pipeline_run_id, url, source_urls)
        except asyncio.CancelledError:
            # The scrape outlives this workflow unless it is told otherwise: cancelling here
            # only stops the poller. Shielded because the workflow is already cancelling, so an
            # unshielded activity would be cancelled before it could be sent.
            if dispatch_mode == _DISPATCH_MODE_LOCAL:
                await asyncio.shield(
                    workflow.execute_activity(
                        cancel_local_run,
                        args=[pipeline_run_id],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                )
            raise
        return await self._handle_conclusion(conclusion, pipeline_run_id)

    async def _dispatch_and_poll(
        self,
        dispatch_mode: str,
        jurisdiction_ocdid: str,
        pipeline_run_id: str,
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        trigger = trigger_local if dispatch_mode == _DISPATCH_MODE_LOCAL else trigger_github_action
        # Never retried. Dispatching is not idempotent — each attempt starts a real GitHub
        # Actions run — and the activity waits for that run to register before returning, so a
        # slow registration used to time it out and dispatch again. Observed 2026-08-17:
        # fourteen runs queued for one scrape. A failure here should surface, not multiply.
        await workflow.execute_activity(
            trigger,
            args=[jurisdiction_ocdid, pipeline_run_id, url, source_urls],
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        return await workflow.execute_activity(
            poll_pipeline_run_status,
            args=[pipeline_run_id],
            start_to_close_timeout=timedelta(minutes=35),
            heartbeat_timeout=timedelta(seconds=60),
        )

    async def _handle_conclusion(self, conclusion: str, pipeline_run_id: str) -> str:
        if conclusion == RunConclusion.SUCCESS:
            await workflow.execute_activity(
                update_pipeline_run_status,
                args=[pipeline_run_id, PipelineRunStatus.SUCCESS],
                start_to_close_timeout=timedelta(seconds=30),
            )
            return conclusion

        # A failed run ends here rather than parking on a `human_approval` signal. Nothing ever
        # sent that signal — the approval UI it was written for was never built — so every
        # failure held its workflow open forever, and because `_dispatch` gathers a slice of
        # children, one of them stalled a whole state scrape.
        #
        # Nothing is lost by ending: the pipeline has already PATCHed ERROR, the issue is filed
        # against the run, and the state page counts it. A retry is a new run with a new id, not
        # a suspended old one — which is what the restart below did anyway.
        workflow.logger.info(f"Run {pipeline_run_id} failed")
        return conclusion


# Fallback only. The real value arrives as a workflow argument, from PIPELINE_RUN_CONCURRENCY
# on the API side — read there rather than here because Temporal replays a workflow, so a value
# that changed between runs would diverge.
DEFAULT_PIPELINE_RUN_CONCURRENCY = 25


@workflow.defn
class StateScrapeWorkflow:
    """A state's scrape, start to finish, as one durable thing.

    It asks the API for its own candidates rather than being handed a list. A Temporal Schedule
    can only pass fixed arguments, so a scheduled scrape can give it a state and nothing else —
    and resolving candidates before starting left orphaned changesets whenever the caller died
    between registering them and starting the run.
    """

    @workflow.run
    async def run(
        self,
        state: str,
        num_jurisdictions: Optional[int] = None,
        created_by_user_id: Optional[str] = None,
        concurrency: int = DEFAULT_PIPELINE_RUN_CONCURRENCY,
    ) -> int:
        slice_size = max(1, concurrency)
        dispatched = 0

        # A slice at a time, claimed as it is dispatched. Claiming the whole state up front and
        # stopping partway would leave every undispatched jurisdiction holding a registered run
        # — and `get_scrape_candidates` excludes non-terminal runs, so those places would drop
        # out of the pool until something swept them. Claiming per slice means the only claimed
        # work is the slice in flight, so stopping needs no compensating release.
        #
        # Terminates three ways: the budget is reached, the state runs out of candidates (the
        # claim returns nothing), or the caller's requested count is met. The claim registers a
        # run for what it hands back, and registered runs are excluded from candidates, so each
        # call returns fresh jurisdictions and the second case always arrives.
        while num_jurisdictions is None or dispatched < num_jurisdictions:
            cap = await workflow.execute_activity(
                budget_cap_reached,
                args=[state],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            if cap:
                workflow.logger.warning(
                    f"{state}: stopping after {dispatched} jurisdictions, {cap} reached"
                )
                break

            wanted = (
                slice_size
                if num_jurisdictions is None
                else min(slice_size, num_jurisdictions - dispatched)
            )
            items = await workflow.execute_activity(
                claim_scrape_candidates,
                args=[state, wanted, created_by_user_id],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            if not items:
                break

            await _dispatch(items, slice_size)
            dispatched += len(items)

        return dispatched


async def _dispatch(items: list[dict], concurrency: int) -> None:
    """A slice at a time, not all at once: a state scrape takes every jurisdiction due — 1,293
    for Michigan — and each one dispatches its own pipeline run.

    Sliced rather than semaphored because a workflow must be deterministic on replay, and a
    fixed slice obviously is.
    """
    for start in range(0, len(items), concurrency):
        handles = []
        for item in items[start : start + concurrency]:
            handle = await workflow.start_child_workflow(
                PeopleCollectorWorkflow.run,
                args=[item["jurisdiction_ocdid"], item["pipeline_run_id"]],
                id=_workflow_id(item["jurisdiction_ocdid"]),
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            )
            handles.append(handle)
        await asyncio.gather(*handles)


# Kept for the workflows already running against it when StateScrapeWorkflow landed; nothing
# starts one any more.
@workflow.defn
class BatchPeopleCollectorWorkflow:
    @workflow.run
    async def run(self, items: list[dict]) -> None:
        await _dispatch(items, DEFAULT_PIPELINE_RUN_CONCURRENCY)
