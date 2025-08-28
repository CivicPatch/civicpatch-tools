import os
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app

client = TestClient(app)

@patch("main.get_server_detail_by_active_api_key")
@patch("main.upload_file_to_storage")
@patch("main.trigger_github_data_intake_workflow")
def test_github_intake_with_real_zip(
    mock_trigger_workflow,
    mock_upload_file,
    mock_get_server_detail,
):
    # Mock dependencies
    mock_get_server_detail.return_value = {
        "user_email": "test@example.com",
        "server_url": "https://example.com"
    }
    mock_upload_file.return_value = "https://storage.example.com/test.zip"
    mock_trigger_workflow.return_value = None

    # Use your real zip file here
    zip_path = "/path/to/your/file.zip"  # <-- Change this to your zip file path
    with open(zip_path, "rb") as f:
        files = {"file": ("file.zip", f, "application/zip")}
        headers = {"authorization": "test-api-key"}
        response = client.post("/api/github_intake", files=files, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "file.zip"
    assert data["status"] == "uploaded"
    assert data["url"] == "https://storage.example.com/test.zip"