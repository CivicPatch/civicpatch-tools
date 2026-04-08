from datetime import timedelta
from typing import Optional

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities.github_activity import trigger_github_action, poll_run_status, trigger_local_job, poll_local_job_status
    from activities.job_status_activity import update_job_status
    from constants import RunConclusion, RunMode
    from shared.utils.statuses import JobStatus

TASK_QUEUE = "people-collector"

_DISPATCH_MODE_LOCAL = "local"


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
        name: Optional[str] = None,
        url: Optional[str] = None,
        source_urls: Optional[list[str]] = None,
    ) -> str:
        await workflow.execute_activity(
            update_job_status,
            args=[request_id, JobStatus.RUNNING],
            start_to_close_timeout=timedelta(seconds=30),
        )

        if dispatch_mode == _DISPATCH_MODE_LOCAL:
            await workflow.execute_activity(
                trigger_local_job,
                args=[jurisdiction_ocdid, request_id, name, url, source_urls],
                start_to_close_timeout=timedelta(minutes=2),
            )
            conclusion = await workflow.execute_activity(
                poll_local_job_status,
                args=[request_id],
                start_to_close_timeout=timedelta(minutes=35),
                heartbeat_timeout=timedelta(seconds=60),
            )
        else:
            run_id = await workflow.execute_activity(
                trigger_github_action,
                args=[jurisdiction_ocdid, request_id],
                start_to_close_timeout=timedelta(minutes=2),
            )
            conclusion = await workflow.execute_activity(
                poll_run_status,
                args=[run_id],
                start_to_close_timeout=timedelta(minutes=35),
                heartbeat_timeout=timedelta(seconds=60),
            )

        if conclusion == RunConclusion.SUCCESS:
            await workflow.execute_activity(
                update_job_status,
                args=[request_id, JobStatus.COMPLETED],
                start_to_close_timeout=timedelta(seconds=30),
            )
            return conclusion

        if conclusion == RunConclusion.FAILURE and dispatch_mode != _DISPATCH_MODE_LOCAL:
            await workflow.execute_activity(
                update_job_status,
                args=[request_id, JobStatus.PAUSED],
                start_to_close_timeout=timedelta(seconds=30),
            )
            workflow.logger.info(f"Job {request_id} paused — waiting for human_approval signal")
            await workflow.wait_condition(lambda: self._approved)
            workflow.logger.info("Received human_approval — triggering resume run")

            resume_run_id = await workflow.execute_activity(
                trigger_github_action,
                args=[jurisdiction_ocdid, request_id, RunMode.RESUME],
                start_to_close_timeout=timedelta(minutes=2),
            )
            resume_conclusion = await workflow.execute_activity(
                poll_run_status,
                args=[resume_run_id],
                start_to_close_timeout=timedelta(minutes=35),
                heartbeat_timeout=timedelta(seconds=60),
            )
            final_status = JobStatus.COMPLETED if resume_conclusion == RunConclusion.SUCCESS else JobStatus.ERROR
            await workflow.execute_activity(
                update_job_status,
                args=[request_id, final_status],
                start_to_close_timeout=timedelta(seconds=30),
            )
            return resume_conclusion

        await workflow.execute_activity(
            update_job_status,
            args=[request_id, JobStatus.ERROR],
            start_to_close_timeout=timedelta(seconds=30),
        )
        return conclusion
