import os

import httpx
from pipelines_environment import get_env_vars

import services.civicpatch_api
from runners.people_collector.schemas import MaybeSendToGitHubStep, PeopleCollectorContext, PipelineStatus
from shared.utils.statuses import PipelineRunStatus
from utils import log_utils, file_utils


async def send_success(context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> MaybeSendToGitHubStep:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 7: {PipelineStatus.SEND_SUCCESS.value}")

    env = get_env_vars()
    SERVICE_API_KEY = env["SERVICE_API_KEY"]
    CIVICPATCH_ORG_URL = env["CIVICPATCH_ORG_URL"]
    request_id = context.request_id
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    if not SERVICE_API_KEY:
        logger.error(f"Generate api key from CRUDDER at {CIVICPATCH_ORG_URL}")
        raise RuntimeError("SERVICE_API_KEY is not set; cannot submit job artifacts.")

    zip_file_path = file_utils.zip_job_artifacts(request_id, jurisdiction_ocdid, include_data=True)
    zip_size_bytes = os.path.getsize(zip_file_path)
    logger.info(f"Submitting job artifacts to {CIVICPATCH_ORG_URL} (zip size: {zip_size_bytes} bytes)")

    response = await services.civicpatch_api.submit_job_artifacts(
        api_client, request_id, jurisdiction_ocdid, zip_file_path, pipeline_run_status=PipelineRunStatus.SUCCESS
    )
    if not response:
        raise RuntimeError("Failed to get a response from Crudder after retries.")

    logger.info(f"submit_job_artifacts response: {response.status_code}")

    if not response.is_success:
        raise RuntimeError(
            f"submit_job_artifacts failed with status {response.status_code}: {response.text}"
        )

    return MaybeSendToGitHubStep(
        status="completed",
        response_status_code=response.status_code,
        response_text=response.text,
    )
