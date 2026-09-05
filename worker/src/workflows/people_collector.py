import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from activities.github_activity import cancel_local_run, trigger_github_action, trigger_local
    from activities.pipeline_run_status_activity import update_pipeline_run_status, poll_pipeline_run_status
    from activities.state_scrape_activity import claim_scrape_candidates
    from constants import RunConclusion
    from shared.utils.statuses import PipelineRunStatus

TASK_QUEUE = "people-collector"

_DISPATCH_MODE_LOCAL = "local"


def _workflow_id(jurisdiction_ocdid: str) -> str:
    safe = jurisdiction_ocdid.replace("/", "-").replace(":", "-")
    return f"people-collector-{safe}"


@workflow.defn
class PeopleCollectorWorkflow:
    def __init__(self) -> None:
        self._approved = False

    @workflow.signal
    def human_approval(self) -> None:
        self._approved = True

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
        return await self._handle_conclusion(conclusion, dispatch_mode, jurisdiction_ocdid, pipeline_run_id, url, source_urls)

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

    async def _handle_conclusion(
        self,
        conclusion: str,
        dispatch_mode: str,
        jurisdiction_ocdid: str,
        pipeline_run_id: str,
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        if conclusion == RunConclusion.SUCCESS:
            await workflow.execute_activity(
                update_pipeline_run_status,
                args=[pipeline_run_id, PipelineRunStatus.SUCCESS],
                start_to_close_timeout=timedelta(seconds=30),
            )
            return conclusion

        # Job stays ERROR in DB. Temporal waits silently for human_approval signal.
        # Frontend approval UI and PAUSED DB state to be added later.
        workflow.logger.info(f"Job {pipeline_run_id} failed — waiting for human_approval signal")
        await workflow.wait_condition(lambda: self._approved)
        workflow.logger.info("Received human_approval — restarting job")

        restart_conclusion = await self._dispatch_and_poll(dispatch_mode, jurisdiction_ocdid, pipeline_run_id, url, source_urls)
        final_status = PipelineRunStatus.SUCCESS if restart_conclusion == RunConclusion.SUCCESS else PipelineRunStatus.ERROR
        await workflow.execute_activity(
            update_pipeline_run_status,
            args=[pipeline_run_id, final_status],
            start_to_close_timeout=timedelta(seconds=30),
        )
        return restart_conclusion


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
        items = await workflow.execute_activity(
            claim_scrape_candidates,
            args=[state, num_jurisdictions, created_by_user_id],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        if not items:
            return 0
        await _dispatch(items, max(1, concurrency))
        return len(items)


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
