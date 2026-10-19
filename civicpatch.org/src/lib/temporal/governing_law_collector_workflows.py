"""The governing_law_collector's workflows: one jurisdiction's run, and a state's worth of them.
Beside the scrape's, on the same queue, sharing its watch and its status activities."""

import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from routers.temporal.governing_law_collector_activities import (
        claim_jurisdictions_for_governing_law_collector,
        governing_law_collector_month_cap_reached,
        trigger_governing_law_collector_local,
        trigger_governing_law_collector_remote,
    )
    from routers.temporal.pipeline_run_activities import (
        cancel_local_pipeline_run,
        poll_pipeline_run_status,
        update_pipeline_run_status,
    )
    from shared.utils.statuses import PipelineRunStatus

    from lib.temporal.types import (
        GOVERNING_LAW_COLLECTOR_EXECUTION_TIMEOUT,
        RunConclusion,
        governing_law_collector_workflow_id,
    )

_DISPATCH_MODE_LOCAL = "local"
_SETTLE_MARGIN = timedelta(minutes=5)
_QUICK = timedelta(seconds=30)


@workflow.defn
class GoverningLawCollectorWorkflow:
    @workflow.run
    async def run(self, jurisdiction_ocdid: str, pipeline_run_id: str, dispatch_mode: str = "remote") -> str:
        await workflow.execute_activity(
            update_pipeline_run_status, args=[pipeline_run_id, PipelineRunStatus.RUNNING], start_to_close_timeout=_QUICK
        )
        local = dispatch_mode == _DISPATCH_MODE_LOCAL
        try:
            await workflow.execute_activity(
                trigger_governing_law_collector_local if local else trigger_governing_law_collector_remote,
                args=[jurisdiction_ocdid, pipeline_run_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            conclusion = await workflow.execute_activity(
                poll_pipeline_run_status,
                args=[pipeline_run_id],
                schedule_to_close_timeout=GOVERNING_LAW_COLLECTOR_EXECUTION_TIMEOUT - _SETTLE_MARGIN,
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
class GoverningLawCollectorStateWorkflow:
    """A state's collection, a slice at a time, as the scrape's state workflow claims its work:
    stopping at the collector's monthly cap, when the state runs out, or at the count asked for."""

    @workflow.run
    async def run(
        self,
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
                governing_law_collector_month_cap_reached, start_to_close_timeout=_QUICK, retry_policy=RetryPolicy(maximum_attempts=3)
            )
            if cap:
                workflow.logger.warning(f"{state}: stopping after {dispatched} jurisdictions, {cap} reached")
                break
            wanted = slice_size if num_jurisdictions is None else min(slice_size, num_jurisdictions - dispatched)
            items = await workflow.execute_activity(
                claim_jurisdictions_for_governing_law_collector,
                args=[state, wanted, created_by_user_id],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            if not items:
                break
            handles = [
                await workflow.start_child_workflow(
                    GoverningLawCollectorWorkflow.run,
                    args=[item["jurisdiction_ocdid"], item["pipeline_run_id"], dispatch_mode],
                    id=governing_law_collector_workflow_id(item["jurisdiction_ocdid"]),
                    id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                )
                for item in items
            ]
            await asyncio.gather(*handles)
            dispatched += len(items)
        return dispatched
