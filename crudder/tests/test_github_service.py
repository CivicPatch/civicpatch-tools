import os
import pytest
from github_service import trigger_github_data_intake_workflow

def test_trigger_github_data_intake_workflow_real():
    github_workflow_token = os.getenv("GITHUB_WORKFLOW_TOKEN")
    user_email = "test@example.com"
    server_url = os.getenv("TEST_API_URL")
    request_id = os.getenv("TEST_REQUEST_ID")
    state = "wa"
    geoid = "5367000"
    zip_file_url = os.getenv("TEST_ZIP_URL")

    assert github_workflow_token, "Set GITHUB_WORKFLOW_TOKEN in your environment"
    assert server_url, "Set TEST_API_URL in your environment"
    assert request_id, "Set TEST_REQUEST_ID in your environment"
    assert zip_file_url, "Set TEST_ZIP_URL in your environment"

    print("Triggering GitHub workflow...")
    result = trigger_github_data_intake_workflow(
        github_workflow_token,
        user_email,
        server_url,
        request_id,
        state,
        geoid,
        zip_file_url
    )
    assert result is True