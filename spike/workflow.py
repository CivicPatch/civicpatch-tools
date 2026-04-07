from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities import trigger_github_action, poll_run_status


@workflow.defn
class PeopleCollectorWorkflow:
    def __init__(self) -> None:
        self._approved = False

    @workflow.signal
    def human_approval(self) -> None:
        self._approved = True

    @workflow.run
    async def run(self, jurisdiction_ocdid: str, request_id: str) -> str:
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

        if conclusion != "success":
            workflow.logger.info(f"Run concluded with '{conclusion}' — waiting for human_approval signal")
            await workflow.wait_condition(lambda: self._approved)
            workflow.logger.info("Received human_approval signal — workflow resuming")

        return conclusion
