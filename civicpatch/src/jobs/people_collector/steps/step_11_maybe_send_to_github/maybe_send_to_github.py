import os

from civicpatch_environment import get_env_vars

import services.civicpatch_api
from jobs.people_collector.schemas import MaybeSendToGitHubStep, PeopleCollectorContext, WorkflowStatus
from utils import cost_utils, log_utils, file_utils


async def maybe_send_to_github(context: PeopleCollectorContext) -> MaybeSendToGitHubStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 11: {WorkflowStatus.SEND_SUCCESS.value}")

    env = get_env_vars()
    SERVICE_API_KEY = env["SERVICE_API_KEY"]
    API_CIVICPATCH_ORG_URL = env["API_CIVICPATCH_ORG_URL"]
    request_id = context.request_id
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    try:
        if not SERVICE_API_KEY:
            logger.error(
                "SERVICE_API_KEY is not set, skipping github workflow dispatch."
            )
            logger.error(f"Generate api key from CRUDDER at {API_CIVICPATCH_ORG_URL}")
            return MaybeSendToGitHubStep(status="skipped_no_token")

        zip_file_path = file_utils.zip_job_artifacts(request_id, jurisdiction_ocdid, include_data=True)
        file_size_bytes = os.path.getsize(zip_file_path)
        logger.info(f"Created zip file at {zip_file_path}, size: {file_size_bytes} bytes")
        cost_utils.add_storage_cost(request_id, jurisdiction_ocdid, file_size_bytes)

        response = await services.civicpatch_api.submit_job_artifacts(
            request_id, jurisdiction_ocdid, zip_file_path, "SUCCESS"
        )
        if not response:
            logger.error("Failed to get a response from Crudder after retries.")
            return MaybeSendToGitHubStep(status="failed_no_response")

        return MaybeSendToGitHubStep(
            status="completed",
            response_status_code=response.status_code,
            response_text=response.text,
        )

    except Exception as e:
        logger.error(f"Error sending to api.civicpatch.org: {e}")
        return MaybeSendToGitHubStep(status="failed", response_text=str(e))
