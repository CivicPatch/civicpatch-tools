"""The pipeline-run workflows: one jurisdiction's run, and a whole state's worth of them.

Moved from the standalone `worker` package on 2026-09-05. They run on their own task queue,
registered by `workers/pipeline_runs.py`, its own process and pod — a different
concurrency budget, because these activities are thin and long-lived where the sync ones are
short and memory-hungry.
"""

import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from routers.temporal.pipeline_run_activities import (
        people_collector_month_cap_reached,
        cancel_local_pipeline_run,
        claim_jurisdictions_for_people_collector,
        poll_pipeline_run_status,
        trigger_people_collector_remote,
        trigger_people_collector_local,
        update_pipeline_run_status,
    )
    from shared.utils.statuses import PipelineIssueType, PipelineRunStatus

    from lib.temporal.types import (
        PEOPLE_COLLECTOR_EXECUTION_TIMEOUT,
        PEOPLE_COLLECTOR_STATE_WORKFLOW,
        PEOPLE_COLLECTOR_WORKFLOW,
        RunConclusion,
    )

_DISPATCH_MODE_LOCAL = "local"
# Room after the watch gives up for the workflow to cancel the scrape and settle the run.
_SETTLE_MARGIN = timedelta(minutes=5)


def _workflow_id(jurisdiction_ocdid: str) -> str:
    safe = jurisdiction_ocdid.replace("/", "-").replace(":", "-")
    return f"people-collector-{safe}"


@workflow.defn(name=PEOPLE_COLLECTOR_WORKFLOW)
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
            conclusion = await self._dispatch_and_poll(
                dispatch_mode, jurisdiction_ocdid, pipeline_run_id, url, source_urls
            )
        except asyncio.CancelledError:
            # The scrape outlives this workflow unless it is told otherwise: cancelling here
            # only stops the poller. Shielded because the workflow is already cancelling, so an
            # unshielded activity would be cancelled before it could be sent.
            if dispatch_mode == _DISPATCH_MODE_LOCAL:
                await asyncio.shield(
                    workflow.execute_activity(
                        cancel_local_pipeline_run,
                        args=[pipeline_run_id],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                )
            raise
        except Exception as exc:
            # Stop the scrape too: left running, it reports into a run already settled.
            if dispatch_mode == _DISPATCH_MODE_LOCAL:
                await workflow.execute_activity(
                    cancel_local_pipeline_run,
                    args=[pipeline_run_id],
                    start_to_close_timeout=timedelta(seconds=30),
                )
            # The failure is filed here because nothing else will: a run that dies mid-scrape
            # uploads no report, so the issue the pipeline would have filed never arrives.
            await workflow.execute_activity(
                update_pipeline_run_status,
                args=[
                    pipeline_run_id,
                    PipelineRunStatus.ERROR,
                    None,
                    PipelineIssueType.PIPELINE_ERROR.value,
                    {"error": str(exc)},
                ],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
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
        trigger = (
            trigger_people_collector_local
            if dispatch_mode == _DISPATCH_MODE_LOCAL
            else trigger_people_collector_remote
        )
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
            # Attempts unbounded: a worker restart ends one, and must not cost the run. A quiet
            # run fails the activity non-retryably. The whole watch ends before the workflow's own
            # timeout, because a *terminated* workflow runs no `except` and nothing settles the run.
            schedule_to_close_timeout=PEOPLE_COLLECTOR_EXECUTION_TIMEOUT - _SETTLE_MARGIN,
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
        # failure held its workflow open forever, and because the state pass waits on its
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


@workflow.defn(name=PEOPLE_COLLECTOR_STATE_WORKFLOW)
class PeopleCollectorStateWorkflow:
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
        dispatch_mode: str = "remote",
    ) -> int:
        limit = max(1, concurrency)
        runs: list[workflow.ChildWorkflowHandle] = []

        # Temporal's sliding-window pattern. One place claimed per run started: claiming ahead
        # and stopping partway would leave unstarted places holding runs the pool excludes.
        while num_jurisdictions is None or len(runs) < num_jurisdictions:
            await workflow.wait_condition(lambda: _running(runs) < limit)
            claimed = await _claim_one(state, created_by_user_id)
            if claimed is None:
                break
            runs.append(await _start(claimed, dispatch_mode))

        await workflow.wait_condition(lambda: _running(runs) == 0)
        return len(runs)


def _running(runs: list[workflow.ChildWorkflowHandle]) -> int:
    # A failed run counts as finished: it has already settled itself.
    return sum(1 for run in runs if not run.done())


async def _claim_one(state: str, created_by_user_id: Optional[str]) -> Optional[dict]:
    cap = await workflow.execute_activity(
        people_collector_month_cap_reached,
        args=[state],
        start_to_close_timeout=timedelta(seconds=30),
        retry_policy=RetryPolicy(maximum_attempts=3),
    )
    if cap:
        workflow.logger.warning(f"{state}: no more claims, {cap} reached")
        return None
    claimed = await workflow.execute_activity(
        claim_jurisdictions_for_people_collector,
        args=[state, 1, created_by_user_id],
        start_to_close_timeout=timedelta(minutes=2),
        retry_policy=RetryPolicy(maximum_attempts=3),
    )
    return claimed[0] if claimed else None


async def _start(item: dict, dispatch_mode: str) -> workflow.ChildWorkflowHandle:
    return await workflow.start_child_workflow(
        PeopleCollectorWorkflow.run,
        args=[item["jurisdiction_ocdid"], item["pipeline_run_id"], dispatch_mode],
        id=_workflow_id(item["jurisdiction_ocdid"]),
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )
