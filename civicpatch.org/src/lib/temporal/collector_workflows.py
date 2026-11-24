"""A state's pass for any pipeline, and one jurisdiction's run for pipelines 1 and 2. The scrape's
own run, `PeopleCollectorWorkflow`, differs enough to keep its own; the pass starts it like the
others. Same queue as the scrape, sharing its watch and status activities."""

import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from routers.temporal.collector_activities import (
        claim_jurisdictions_for_collector,
        collector_month_cap_reached,
        trigger_collector_local,
        trigger_collector_remote,
    )
    from routers.temporal.pipeline_run_activities import (
        cancel_local_pipeline_run,
        claim_jurisdictions_for_people_collector,
        people_collector_month_cap_reached,
        poll_pipeline_run_status,
        update_pipeline_run_status,
    )
    from shared.utils.statuses import PipelineRunKind, PipelineRunStatus

    from lib.temporal.pipeline_run_workflows import PeopleCollectorWorkflow

    from lib.temporal.types import (
        COLLECTOR_EXECUTION_TIMEOUT,
        COLLECTOR_STATE_WORKFLOW,
        COLLECTOR_WORKFLOW,
        RunConclusion,
        collector_workflow_id,
    )

_DISPATCH_MODE_LOCAL = "local"
_SETTLE_MARGIN = timedelta(minutes=5)
_QUICK = timedelta(seconds=30)
_RETRY_THRICE = RetryPolicy(maximum_attempts=3)
# Fallback only. The real value arrives as a workflow argument, from PIPELINE_RUN_CONCURRENCY on
# the API side: read there because Temporal replays a workflow, and a value that changed between
# runs would diverge. A schedule passes no concurrency, so its passes use this.
DEFAULT_CONCURRENCY = 25


@workflow.defn(name=COLLECTOR_WORKFLOW)
class CollectorWorkflow:
    @workflow.run
    async def run(self, kind: str, jurisdiction_ocdid: str, pipeline_run_id: str, dispatch_mode: str = "remote") -> str:
        await workflow.execute_activity(
            update_pipeline_run_status, args=[pipeline_run_id, PipelineRunStatus.RUNNING], start_to_close_timeout=_QUICK
        )
        local = dispatch_mode == _DISPATCH_MODE_LOCAL
        try:
            await workflow.execute_activity(
                trigger_collector_local if local else trigger_collector_remote,
                args=[kind, jurisdiction_ocdid, pipeline_run_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            conclusion = await workflow.execute_activity(
                poll_pipeline_run_status,
                args=[pipeline_run_id],
                schedule_to_close_timeout=COLLECTOR_EXECUTION_TIMEOUT - _SETTLE_MARGIN,
                heartbeat_timeout=timedelta(seconds=60),
            )
        except asyncio.CancelledError:
            if local:
                await asyncio.shield(
                    workflow.execute_activity(cancel_local_pipeline_run, args=[pipeline_run_id], start_to_close_timeout=_QUICK)
                )
            raise
        except Exception:
            if local:
                await workflow.execute_activity(cancel_local_pipeline_run, args=[pipeline_run_id], start_to_close_timeout=_QUICK)
            await workflow.execute_activity(
                update_pipeline_run_status,
                args=[pipeline_run_id, PipelineRunStatus.ERROR],
                start_to_close_timeout=_QUICK,
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            raise
        if conclusion == RunConclusion.SUCCESS:
            await workflow.execute_activity(
                update_pipeline_run_status, args=[pipeline_run_id, PipelineRunStatus.SUCCESS], start_to_close_timeout=_QUICK
            )
        return conclusion


@workflow.defn(name=COLLECTOR_STATE_WORKFLOW)
class CollectorStateWorkflow:
    """One pipeline's pass over a state, as Temporal's sliding-window pattern
    (https://docs.temporal.io/design-patterns/sliding-window), with child handles in place of the
    sample's completion signals: no `continue_as_new`, since a state's places fit one history."""

    @workflow.run
    async def run(
        self,
        kind: str,
        state: str,
        num_jurisdictions: Optional[int] = None,
        created_by_user_id: Optional[str] = None,
        concurrency: int = DEFAULT_CONCURRENCY,
        dispatch_mode: str = "remote",
    ) -> int:
        limit = max(1, concurrency)
        runs: list[workflow.ChildWorkflowHandle] = []

        # One place claimed per run started: claiming ahead and stopping partway would leave the
        # unstarted places holding registered runs, which the candidate pool excludes.
        while num_jurisdictions is None or len(runs) < num_jurisdictions:
            await workflow.wait_condition(lambda: _running(runs) < limit)
            claimed = await _claim_one(kind, state, created_by_user_id)
            if claimed is None:
                break
            runs.append(await _start(kind, claimed, dispatch_mode))

        await workflow.wait_condition(lambda: _running(runs) == 0)
        return len(runs)


def _running(runs: list[workflow.ChildWorkflowHandle]) -> int:
    # A failed run counts as finished: it has already settled itself.
    return sum(1 for run in runs if not run.done())


async def _claim_one(kind: str, state: str, created_by_user_id: Optional[str]) -> Optional[dict]:
    cap = await _cap_reached(kind, state)
    if cap:
        workflow.logger.warning(f"{kind} {state}: no more claims, {cap} reached")
        return None
    claimed = await _claim(kind, state, created_by_user_id)
    return claimed[0] if claimed else None


async def _cap_reached(kind: str, state: str) -> Optional[str]:
    if kind == PipelineRunKind.PEOPLE_COLLECTOR:
        return await workflow.execute_activity(
            people_collector_month_cap_reached, args=[state], start_to_close_timeout=_QUICK, retry_policy=_RETRY_THRICE
        )
    return await workflow.execute_activity(
        collector_month_cap_reached, args=[kind, state], start_to_close_timeout=_QUICK, retry_policy=_RETRY_THRICE
    )


async def _claim(kind: str, state: str, created_by_user_id: Optional[str]) -> list[dict]:
    if kind == PipelineRunKind.PEOPLE_COLLECTOR:
        return await workflow.execute_activity(
            claim_jurisdictions_for_people_collector,
            args=[state, 1, created_by_user_id],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=_RETRY_THRICE,
        )
    return await workflow.execute_activity(
        claim_jurisdictions_for_collector,
        args=[kind, state, 1, created_by_user_id],
        start_to_close_timeout=timedelta(minutes=2),
        retry_policy=_RETRY_THRICE,
    )


async def _start(kind: str, item: dict, dispatch_mode: str) -> workflow.ChildWorkflowHandle:
    jurisdiction_ocdid = item["jurisdiction_ocdid"]
    pipeline_run_id = item["pipeline_run_id"]
    if kind == PipelineRunKind.PEOPLE_COLLECTOR:
        child, args = PeopleCollectorWorkflow.run, [jurisdiction_ocdid, pipeline_run_id, dispatch_mode]
    else:
        child, args = CollectorWorkflow.run, [kind, jurisdiction_ocdid, pipeline_run_id, dispatch_mode]
    return await workflow.start_child_workflow(
        child,
        args=args,
        id=collector_workflow_id(kind, jurisdiction_ocdid),
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )
