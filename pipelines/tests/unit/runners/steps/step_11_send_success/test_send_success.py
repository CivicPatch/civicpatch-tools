import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from runners.people_collector.steps.step_11_send_success.send_success import send_success
from runners.people_collector.schemas import MaybeSendToGitHubStep
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

MODULE = "runners.people_collector.steps.step_11_send_success.send_success"

_ENV = {"SERVICE_API_KEY": "token", "CIVICPATCH_ORG_URL": "https://civicpatch.org"}


def _make_response(status_code: int, text: str = ""):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.is_success = 200 <= status_code < 300
    return response


@pytest.fixture(autouse=True)
def mock_logger():
    with patch(f"{MODULE}.log_utils.get_pipeline_run_logger", return_value=MagicMock()):
        yield


@pytest.fixture
def context():
    return pipeline_run_context_factory(steps={})


@pytest.mark.asyncio
async def test_send_success_raises_when_no_service_api_key(context):
    with patch(f"{MODULE}.get_env_vars", return_value={**_ENV, "SERVICE_API_KEY": ""}):
        with pytest.raises(RuntimeError, match="SERVICE_API_KEY"):
            await send_success(context, api_client=MagicMock())


@pytest.mark.asyncio
async def test_send_success_returns_completed_on_2xx(context):
    response = _make_response(200, "ok")
    with (
        patch(f"{MODULE}.get_env_vars", return_value=_ENV),
        patch(f"{MODULE}.file_utils.zip_job_artifacts", return_value="/tmp/fake.zip"),
        patch(f"{MODULE}.os.path.getsize", return_value=1024),
        patch(f"{MODULE}.services.civicpatch_api.submit_job_artifacts", new=AsyncMock(return_value=response)),
    ):
        result = await send_success(context, api_client=MagicMock())

    assert result == MaybeSendToGitHubStep(status="completed", response_status_code=200, response_text="ok")


@pytest.mark.asyncio
async def test_send_success_raises_on_server_error(context):
    response = _make_response(500, "boom")
    with (
        patch(f"{MODULE}.get_env_vars", return_value=_ENV),
        patch(f"{MODULE}.file_utils.zip_job_artifacts", return_value="/tmp/fake.zip"),
        patch(f"{MODULE}.os.path.getsize", return_value=1024),
        patch(f"{MODULE}.services.civicpatch_api.submit_job_artifacts", new=AsyncMock(return_value=response)),
    ):
        with pytest.raises(RuntimeError, match="500"):
            await send_success(context, api_client=MagicMock())


@pytest.mark.asyncio
async def test_send_success_raises_on_redirect(context):
    # A redirect means the POST never reached the real handler (the client
    # doesn't follow redirects) — this must not be treated as success.
    response = _make_response(302, "")
    with (
        patch(f"{MODULE}.get_env_vars", return_value=_ENV),
        patch(f"{MODULE}.file_utils.zip_job_artifacts", return_value="/tmp/fake.zip"),
        patch(f"{MODULE}.os.path.getsize", return_value=1024),
        patch(f"{MODULE}.services.civicpatch_api.submit_job_artifacts", new=AsyncMock(return_value=response)),
    ):
        with pytest.raises(RuntimeError, match="302"):
            await send_success(context, api_client=MagicMock())


@pytest.mark.asyncio
async def test_send_success_raises_on_falsy_response(context):
    with (
        patch(f"{MODULE}.get_env_vars", return_value=_ENV),
        patch(f"{MODULE}.file_utils.zip_job_artifacts", return_value="/tmp/fake.zip"),
        patch(f"{MODULE}.os.path.getsize", return_value=1024),
        patch(f"{MODULE}.services.civicpatch_api.submit_job_artifacts", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(RuntimeError):
            await send_success(context, api_client=MagicMock())
