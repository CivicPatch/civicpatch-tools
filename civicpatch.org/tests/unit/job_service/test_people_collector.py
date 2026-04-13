import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from core.people_collector import handle_submit_job_artifacts
from schemas.requests import HandleSubmitJobArtifactsRequest, ServerDetail
from shared.utils.statuses import JobStatus


def make_request(**kwargs):
    defaults = dict(
        request_id="test-request-id",
        jurisdiction_ocdid="ocd-division/country:us/state:ca/place:oakland",
        server_detail=ServerDetail(user_email="test@civicpatch.org", server_url="civicpatch.org"),
        zip_path="/tmp/test.zip",
        temp_dir="/tmp/test",
        job_status="ERROR",
    )
    return HandleSubmitJobArtifactsRequest(**{**defaults, **kwargs})


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_submit_job_artifacts_updates_status_to_error_on_failure():
    request = make_request()
    with (
        patch(
            "core.people_collector._handle_submit_job_artifacts",
            new_callable=AsyncMock,
            side_effect=Exception("storage unavailable"),
        ),
        patch(
            "core.people_collector.update_job_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
    ):
        with pytest.raises(Exception, match="storage unavailable"):
            await handle_submit_job_artifacts(request)

        mock_update_status.assert_awaited_once_with(
            "test-request-id", status=JobStatus.ERROR, progress=None
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_handle_submit_job_artifacts_does_not_update_status_on_success():
    request = make_request()
    mock_response = MagicMock()
    with (
        patch(
            "core.people_collector._handle_submit_job_artifacts",
            new_callable=AsyncMock,
            return_value=mock_response,
        ),
        patch(
            "core.people_collector.update_job_status",
            new_callable=AsyncMock,
        ) as mock_update_status,
    ):
        result = await handle_submit_job_artifacts(request)

        assert result == mock_response
        mock_update_status.assert_not_awaited()
