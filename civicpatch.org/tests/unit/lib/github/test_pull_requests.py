from unittest.mock import AsyncMock, patch

import pytest

from lib.github.pull_requests import PrAuthor, open_attributed_pr, repo_owner_and_name

BRANCH = "civicpatch/jurisdiction-edit/2025-01-01-abc"
REPO_URL = "https://example.test/repos/CivicPatch/open-data"
FORK_URL = "https://example.test/repos/CivicPatch/jurisdictions"
PR_HEADERS = {"Authorization": "Bearer jurisdictions-sync-token"}
FORK_HEADERS = {"Authorization": "Bearer regular-token"}
AUTHOR = PrAuthor(name="Alice", email="alice@example.com")


async def _open(create_branch_result=None):
    with (
        patch(
            "lib.github.pull_requests.github_api_service.create_branch",
            new_callable=AsyncMock,
            return_value=create_branch_result,
        ) as mock_create_branch,
        patch(
            "lib.github.pull_requests.github_api_service.upsert_github_file",
            new_callable=AsyncMock,
            return_value="https://example.test/commit/1",
        ) as mock_upsert,
        patch(
            "lib.github.pull_requests.github_api_service.create_pull_request",
            new_callable=AsyncMock,
            return_value=(7, "https://example.test/pull/7"),
        ) as mock_create_pr,
    ):
        result = await open_attributed_pr(
            branch_name=BRANCH,
            file_path="data_source/tx/local/jurisdictions.yml",
            content="jurisdictions: []\n",
            commit_message="Update url",
            pull_request_title="Jurisdiction edit",
            pull_request_body="Changes",
            author=AUTHOR,
            labels=("civicpatch:maintainer",),
            repo_url=REPO_URL,
            headers=PR_HEADERS,
            fork_repo_url=FORK_URL,
            fork_headers=FORK_HEADERS,
        )
    return result, mock_create_branch, mock_upsert, mock_create_pr


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_regular_bot_writes_the_fork_from_the_repos_main():
    _, mock_create_branch, mock_upsert, _ = await _open()

    branch_kwargs = mock_create_branch.call_args.kwargs
    assert (branch_kwargs["repo_url"], branch_kwargs["headers"], branch_kwargs["base_repo_url"]) == (
        FORK_URL,
        FORK_HEADERS,
        REPO_URL,
    )
    assert (mock_upsert.call_args.kwargs["repo_url"], mock_upsert.call_args.kwargs["headers"]) == (
        FORK_URL,
        FORK_HEADERS,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_the_jurisdictions_bot_opens_the_pr_on_the_repo_from_the_fork():
    result, _, _, mock_create_pr = await _open()

    assert result == (7, "https://example.test/pull/7")
    head = mock_create_pr.call_args.args[0]
    kwargs = mock_create_pr.call_args.kwargs
    assert head == f"CivicPatch:{BRANCH}"
    assert (kwargs["repo_url"], kwargs["headers"], kwargs["head_repo"]) == (REPO_URL, PR_HEADERS, "jurisdictions")
    assert kwargs["labels"] == ["civicpatch:maintainer"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_branch_that_cannot_be_created_opens_nothing():
    (number, error), _, mock_upsert, mock_create_pr = await _open(create_branch_result="branch already exists")

    assert number is None
    assert "branch already exists" in error
    mock_upsert.assert_not_awaited()
    mock_create_pr.assert_not_awaited()


@pytest.mark.unit
def test_a_repos_owner_and_name_come_from_its_url():
    assert repo_owner_and_name(FORK_URL + "/") == ("CivicPatch", "jurisdictions")
