"""The collectors' workflows, one jurisdiction's run and a state's worth of them, for every
`PipelineRunKind` in `COLLECTOR_RUN_KINDS`: the kind is an argument, and the doors, the claim and
the budget follow from it. Beside the scrape's, on the same queue, sharing its watch and status
activities."""

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
        poll_pipeline_run_status,
        update_pipeline_run_status,
    )
    from shared.utils.statuses import PipelineRunStatus

    from lib.temporal.types import COLLECTOR_EXECUTION_TIMEOUT, RunConclusion, collector_workflow_id

_DISPATCH_MODE_LOCAL = "local"
_SETTLE_MARGIN = timedelta(minutes=5)
_QUICK = timedelta(seconds=30)


@workflow.defn
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


@workflow.defn
class CollectorStateWorkflow:
    """A state's collection, a slice at a time, as the scrape's state workflow claims its work:
    stopping at the collector's monthly cap, when the state runs out, or at the count asked for."""

    @workflow.run
    async def run(
        self,
        kind: str,
        state: str,
        num_jurisdictions: Optional[int] = None,
        created_by_user_id: Optional[str] = None,
        concurrency: int = 5,
        dispatch_mode: str = "remote",
    ) -> int:
        slice_size = max(1, concurrency)
        dispatched = 0
        while num_jurisdictions is None or dispatched < num_jurisdictions:
            cap = await workflow.execute_activity(
                collector_month_cap_reached, args=[kind], start_to_close_timeout=_QUICK, retry_policy=RetryPolicy(maximum_attempts=3)
            )
            if cap:
                workflow.logger.warning(f"{kind} {state}: stopping after {dispatched} jurisdictions, {cap} reached")
                break
            wanted = slice_size if num_jurisdictions is None else min(slice_size, num_jurisdictions - dispatched)
            items = await workflow.execute_activity(
                claim_jurisdictions_for_collector,
                args=[kind, state, wanted, created_by_user_id],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            if not items:
                break
            handles = [
                await workflow.start_child_workflow(
                    CollectorWorkflow.run,
                    args=[kind, item["jurisdiction_ocdid"], item["pipeline_run_id"], dispatch_mode],
                    id=collector_workflow_id(kind, item["jurisdiction_ocdid"]),
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )
                for item in items
            ]
            await asyncio.gather(*handles)
            dispatched += len(items)
        return dispatched
