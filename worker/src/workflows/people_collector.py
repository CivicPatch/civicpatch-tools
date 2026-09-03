import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from activities.github_activity import cancel_local_run, trigger_github_action, trigger_local
    from activities.pipeline_run_status_activity import update_pipeline_run_status, poll_pipeline_run_status
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
        changeset_id: str,
        dispatch_mode: str = "remote",
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        await workflow.execute_activity(
            update_pipeline_run_status,
            args=[changeset_id, PipelineRunStatus.RUNNING],
            start_to_close_timeout=timedelta(seconds=30),
        )
        try:
            conclusion = await self._dispatch_and_poll(dispatch_mode, jurisdiction_ocdid, changeset_id, url, source_urls)
        except asyncio.CancelledError:
            # The scrape outlives this workflow unless it is told otherwise: cancelling here
            # only stops the poller. Shielded because the workflow is already cancelling, so an
            # unshielded activity would be cancelled before it could be sent.
            if dispatch_mode == _DISPATCH_MODE_LOCAL:
                await asyncio.shield(
                    workflow.execute_activity(
                        cancel_local_run,
                        args=[changeset_id],
                        start_to_close_timeout=timedelta(seconds=30),
                    )
                )
            raise
        return await self._handle_conclusion(conclusion, dispatch_mode, jurisdiction_ocdid, changeset_id, url, source_urls)

    async def _dispatch_and_poll(
        self,
        dispatch_mode: str,
        jurisdiction_ocdid: str,
        changeset_id: str,
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
            args=[jurisdiction_ocdid, changeset_id, url, source_urls],
            start_to_close_timeout=timedelta(minutes=5),
            heartbeat_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
        return await workflow.execute_activity(
            poll_pipeline_run_status,
            args=[changeset_id],
            start_to_close_timeout=timedelta(minutes=35),
            heartbeat_timeout=timedelta(seconds=60),
        )

    async def _handle_conclusion(
        self,
        conclusion: str,
        dispatch_mode: str,
        jurisdiction_ocdid: str,
        changeset_id: str,
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        if conclusion == RunConclusion.SUCCESS:
            await workflow.execute_activity(
                update_pipeline_run_status,
                args=[changeset_id, PipelineRunStatus.SUCCESS],
                start_to_close_timeout=timedelta(seconds=30),
            )
            return conclusion

        # Job stays ERROR in DB. Temporal waits silently for human_approval signal.
        # Frontend approval UI and PAUSED DB state to be added later.
        workflow.logger.info(f"Job {changeset_id} failed — waiting for human_approval signal")
        await workflow.wait_condition(lambda: self._approved)
        workflow.logger.info("Received human_approval — restarting job")

        restart_conclusion = await self._dispatch_and_poll(dispatch_mode, jurisdiction_ocdid, changeset_id, url, source_urls)
        final_status = PipelineRunStatus.SUCCESS if restart_conclusion == RunConclusion.SUCCESS else PipelineRunStatus.ERROR
        await workflow.execute_activity(
            update_pipeline_run_status,
            args=[changeset_id, final_status],
            start_to_close_timeout=timedelta(seconds=30),
        )
        return restart_conclusion


@workflow.defn
class BatchPeopleCollectorWorkflow:
    @workflow.run
    async def run(self, items: list[dict]) -> None:
        handles = []
        for item in items:
            handle = await workflow.start_child_workflow(
                PeopleCollectorWorkflow.run,
                args=[item["jurisdiction_ocdid"], item["changeset_id"]],
                id=_workflow_id(item["jurisdiction_ocdid"]),
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            )
            handles.append(handle)
        await asyncio.gather(*handles)
