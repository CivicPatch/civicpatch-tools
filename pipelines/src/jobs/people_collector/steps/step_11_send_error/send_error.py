import os

from pipelines_environment import get_env_vars

import services.civicpatch_api
from jobs.people_collector.schemas import MaybeSendToGitHubStep, PeopleCollectorContext, PipelineStatus
from utils import cost_utils, log_utils, file_utils


async def send_error(context: PeopleCollectorContext) -> MaybeSendToGitHubStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step: {PipelineStatus.SEND_ERROR.value}")

    env = get_env_vars()
    if not env.get("SERVICE_API_KEY"):
        logger.error("SERVICE_API_KEY is not set, skipping error log upload.")
        return MaybeSendToGitHubStep(status="skipped_no_token")

    try:
        zip_file_path = file_utils.zip_job_artifacts(
            context.request_id, context.data.jurisdiction_ocdid, include_data=False
        )
        file_size_bytes = os.path.getsize(zip_file_path)
        cost_utils.add_storage_cost(context.request_id, context.data.jurisdiction_ocdid, file_size_bytes)

        response = await services.civicpatch_api.submit_job_artifacts(
            context.request_id, context.data.jurisdiction_ocdid, zip_file_path, job_status="ERROR"
        )
        if not response:
            return MaybeSendToGitHubStep(status="failed_no_response")

        return MaybeSendToGitHubStep(
            status="completed",
            response_status_code=response.status_code,
            response_text=response.text,
        )

    except Exception as e:
        logger.error(f"Error uploading error logs: {e}")
        return MaybeSendToGitHubStep(status="failed", response_text=str(e))
