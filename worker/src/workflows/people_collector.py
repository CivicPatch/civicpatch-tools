import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from activities.github_activity import trigger_github_action, trigger_local
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
        request_id: str,
        dispatch_mode: str = "remote",
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        await workflow.execute_activity(
            update_pipeline_run_status,
            args=[request_id, PipelineRunStatus.RUNNING],
            start_to_close_timeout=timedelta(seconds=30),
        )
        conclusion = await self._dispatch_and_poll(dispatch_mode, jurisdiction_ocdid, request_id, url, source_urls)
        return await self._handle_conclusion(conclusion, dispatch_mode, jurisdiction_ocdid, request_id, url, source_urls)

    async def _dispatch_and_poll(
        self,
        dispatch_mode: str,
        jurisdiction_ocdid: str,
        request_id: str,
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        trigger = trigger_local if dispatch_mode == _DISPATCH_MODE_LOCAL else trigger_github_action
        await workflow.execute_activity(
            trigger,
            args=[jurisdiction_ocdid, request_id, url, source_urls],
            start_to_close_timeout=timedelta(minutes=2),
            heartbeat_timeout=timedelta(seconds=30),
        )
        return await workflow.execute_activity(
            poll_pipeline_run_status,
            args=[request_id],
            start_to_close_timeout=timedelta(minutes=35),
            heartbeat_timeout=timedelta(seconds=60),
        )

    async def _handle_conclusion(
        self,
        conclusion: str,
        dispatch_mode: str,
        jurisdiction_ocdid: str,
        request_id: str,
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        if conclusion == RunConclusion.SUCCESS:
            await workflow.execute_activity(
                update_pipeline_run_status,
                args=[request_id, PipelineRunStatus.SUCCESS],
                start_to_close_timeout=timedelta(seconds=30),
            )
            return conclusion

        # Job stays ERROR in DB. Temporal waits silently for human_approval signal.
        # Frontend approval UI and PAUSED DB state to be added later.
        workflow.logger.info(f"Job {request_id} failed — waiting for human_approval signal")
        await workflow.wait_condition(lambda: self._approved)
        workflow.logger.info("Received human_approval — restarting job")

        restart_conclusion = await self._dispatch_and_poll(dispatch_mode, jurisdiction_ocdid, request_id, url, source_urls)
        final_status = PipelineRunStatus.SUCCESS if restart_conclusion == RunConclusion.SUCCESS else PipelineRunStatus.ERROR
        await workflow.execute_activity(
            update_pipeline_run_status,
            args=[request_id, final_status],
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
                args=[item["jurisdiction_ocdid"], item["request_id"]],
                id=_workflow_id(item["jurisdiction_ocdid"]),
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            )
            handles.append(handle)
        await asyncio.gather(*handles)
