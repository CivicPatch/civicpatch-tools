from unittest.mock import AsyncMock, patch

import pytest

from lib.github.pr import PrAuthor, open_attributed_pr

BRANCH = "civicpatch/jurisdiction-edit/2025-01-01-abc"
REPO_URL = "https://api.github.com/repos/openstates/jurisdictions"
HEADERS = {"Authorization": "Bearer custom-token", "X-GitHub-Api-Version": "2022-11-28"}
AUTHOR = PrAuthor(name="Alice", email="alice@example.com")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_attributed_pr_threads_repo_url_and_headers():
    with (
        patch(
            "lib.github.pr.github_api_service.create_branch",
            new_callable=AsyncMock,
            return_value=None,
        ) as mock_create_branch,
        patch(
            "lib.github.pr.github_api_service.upsert_github_file",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_upsert,
        patch(
            "lib.github.pr.github_api_service.create_pull_request",
            new_callable=AsyncMock,
            return_value=(7, "https://github.com/openstates/jurisdictions/pull/7"),
        ) as mock_create_pr,
    ):
        pr_number, pr_url = await open_attributed_pr(
            branch_name=BRANCH,
            file_path="data_source/tx/jurisdictions.yml",
            content="- id: test\n",
            commit_message="Update metadata",
            pull_request_title="Jurisdiction edit",
            pull_request_body="Updating metadata.",
            author=AUTHOR,
            repo_url=REPO_URL,
            headers=HEADERS,
        )

    assert pr_number == 7

    mock_create_branch.assert_awaited_once()
    _, kwargs = mock_create_branch.call_args
    assert kwargs["repo_url"] == REPO_URL
    assert kwargs["headers"] == HEADERS

    mock_upsert.assert_awaited_once()
    _, kwargs = mock_upsert.call_args
    assert kwargs["repo_url"] == REPO_URL
    assert kwargs["headers"] == HEADERS

    mock_create_pr.assert_awaited_once()
    _, kwargs = mock_create_pr.call_args
    assert kwargs["repo_url"] == REPO_URL
    assert kwargs["headers"] == HEADERS


@pytest.mark.unit
@pytest.mark.asyncio
async def test_open_attributed_pr_returns_error_on_branch_failure():
    with patch(
        "lib.github.pr.github_api_service.create_branch",
        new_callable=AsyncMock,
        return_value="branch already exists",
    ):
        pr_number, error = await open_attributed_pr(
            branch_name=BRANCH,
            file_path="data_source/tx/jurisdictions.yml",
            content="- id: test\n",
            commit_message="Update",
            pull_request_title="Title",
            pull_request_body="Body",
            author=AUTHOR,
        )

    assert pr_number is None
    assert "branch already exists" in error
