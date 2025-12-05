import os
import zipfile

import requests

from jobs.people_collector.schemas import (
    MaybeSendToGitHubStep, PeopleCollectorContext, WorkflowStatus
)
from utils import cost_utils, log_utils
from shared.utils import id_utils
from shared.utils.data_path_utils import (
    get_data_source_path_for_jurisdiction_id,
    get_data_file_path,
)
from utils.request_utils import with_retry

GITHUB_WORKFLOW_DISPATCH_URL = "https://api.github.com/repos/your-username/your-repo/actions/workflows/your-workflow.yml/dispatches"


def maybe_send_to_github(context: PeopleCollectorContext) -> MaybeSendToGitHubStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_id)
    logger.info(f"Step 10: {WorkflowStatus.MAYBE_SEND_TO_GITHUB.value}")

    # https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28#create-a-workflow-dispatch-event
    # https://github.com/android-sms-gateway/example-webhooks-fastapi/blob/master/main.py
    API_CIVICPATCH_ORG_TOKEN = os.getenv("API_CIVICPATCH_ORG_TOKEN")
    API_CIVICPATCH_ORG_URL = os.getenv("API_CIVICPATCH_ORG_URL", "https://api.civicpatch.org")
    CRUDDER_UPLOAD_URL = f"{API_CIVICPATCH_ORG_URL}/api/internal/pipelines/github_intake"
    request_id = context.request_id
    jurisdiction_id = context.data.jurisdiction_id
    logger.info(f"CRUDDER_UPLOAD_URL: {CRUDDER_UPLOAD_URL}")

    try:
        if not API_CIVICPATCH_ORG_TOKEN:
            logger.error(
                "API_CIVICPATCH_ORG_TOKEN is not set, skipping github workflow dispatch."
            )
            logger.error(f"Generate api key from CRUDDER at {API_CIVICPATCH_ORG_URL}")

            return MaybeSendToGitHubStep(status="skipped_no_token")

        zip_file_path = zip_files(context.request_id, context.data.jurisdiction_id)
        file_size_bytes = os.path.getsize(zip_file_path)
        logger.info(
            f"Created zip file at {zip_file_path}, size: {file_size_bytes} bytes"
        )
        cost_utils.add_storage_cost(request_id, jurisdiction_id, file_size_bytes)

        headers = {
            "Authorization": API_CIVICPATCH_ORG_TOKEN,
        }

        files = {
            "file": (
                os.path.basename(zip_file_path),
                open(zip_file_path, "rb"),
                "application/zip",
            )
        }

        # Add metadata in the request body
        data = {
            "request_id": context.request_id,
            "jurisdiction_id": context.data.jurisdiction_id,
        }

        response = with_retry(
            logger,
            max_retries=5,
            func=lambda: requests.post(
                CRUDDER_UPLOAD_URL, headers=headers, files=files, data=data
            ),
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


def zip_files(request_id, jurisdiction_id):
    data_municipality_file = get_data_file_path(jurisdiction_id)
    data_source_municipality_path = get_data_source_path_for_jurisdiction_id(jurisdiction_id)

    git_branch_name = id_utils.jurisdiction_id_to_git_branch(
        jurisdiction_id, request_id
    )
    zip_file_name = f"{git_branch_name}.zip"
    zip_file_path = os.path.join("crudder_data", zip_file_name)

    # Ensure the crudder_data directory exists
    os.makedirs(os.path.dirname(zip_file_path), exist_ok=True)

    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add data_source files - preserve structure starting from "data_source/"
        for root, _dirs, files in os.walk(data_source_municipality_path):
            for file in files:
                file_path = os.path.join(root, file)
                # Keep the "data_source/..." structure in the zip
                arcname = f"data_source/{os.path.relpath(file_path, data_source_municipality_path.split('data_source/')[0] + 'data_source/')}"
                zipf.write(file_path, arcname)

        # Add data municipality file - preserve structure starting from "data/"
        # Assuming data_municipality_file is like "/app/data/wa/seattle.yml"
        data_dir = data_municipality_file.split("data/")[0] + "data/"
        data_arcname = f"data/{os.path.relpath(data_municipality_file, data_dir)}"
        zipf.write(data_municipality_file, data_arcname)

    return zip_file_path
