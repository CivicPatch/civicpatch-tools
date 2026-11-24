"""One jurisdiction's scrape run. A state's pass, for every pipeline, is `collector_workflows`.

Moved from the standalone `worker` package on 2026-09-05. They run on their own task queue,
registered by `workers/pipeline_runs.py`, its own process and pod — a different
concurrency budget, because these activities are thin and long-lived where the sync ones are
short and memory-hungry.
"""

import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from routers.temporal.pipeline_run_activities import (
        cancel_local_pipeline_run,
        poll_pipeline_run_status,
        trigger_people_collector_remote,
        trigger_people_collector_local,
        update_pipeline_run_status,
    )
    from shared.utils.statuses import PipelineIssueType, PipelineRunStatus

    from lib.temporal.types import (
        PEOPLE_COLLECTOR_EXECUTION_TIMEOUT,
        PEOPLE_COLLECTOR_WORKFLOW,
        RunConclusion,
    )

_DISPATCH_MODE_LOCAL = "local"
# Room after the watch gives up for the workflow to cancel the scrape and settle the run.
_SETTLE_MARGIN = timedelta(minutes=5)


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
