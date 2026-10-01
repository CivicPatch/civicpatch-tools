"""A labelled PR is only opened if its labels land: the label decides whether it may merge."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.github.api import create_pull_request

REPO_URL = "https://example.test/repos/jurisdictions"
HEADERS = {"Authorization": "Bearer sync-token"}


def _client_creating_pr(number: int) -> AsyncMock:
    response = MagicMock(status_code=201)
    response.json.return_value = {"number": number, "html_url": f"https://example.test/pull/{number}"}
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=response)
    return client


async def _open(labels_applied: bool):
    with (
        patch("lib.github.api._get_github_config", return_value=("", "", "", REPO_URL)),
        patch("lib.github.api.httpx.AsyncClient", return_value=_client_creating_pr(5)),
        patch("lib.github.api.add_pr_labels", new_callable=AsyncMock, return_value=labels_applied),
        patch("lib.github.api.close_pull_request", new_callable=AsyncMock) as mock_close,
    ):
        result = await create_pull_request(
            "civicpatch/government-form/x",
            title="Government form",
            repo_url=REPO_URL,
            headers=HEADERS,
            labels=["civicpatch:system"],
        )
    return result, mock_close


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_pr_whose_labels_fail_is_closed_and_reported():
    (number, error), mock_close = await _open(labels_applied=False)

    assert number is None
    assert "Failed to label PR #5" in error
    mock_close.assert_awaited_once_with(5, repo_url=REPO_URL, headers=HEADERS)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_fork_pr_names_its_fork_and_asks_for_no_maintainer_edits():
    """Both found against GitHub 2026-09-30: a bare `head_repo` is "head invalid", and the bot
    opening the PR cannot write the fork, so it cannot grant maintainer edits."""
    client = _client_creating_pr(5)
    with (
        patch("lib.github.api._get_github_config", return_value=("", "", "", REPO_URL)),
        patch("lib.github.api.httpx.AsyncClient", return_value=client),
    ):
        await create_pull_request(
            "CivicPatch:civicpatch/jurisdiction-edit/x",
            title="Government form",
            repo_url=REPO_URL,
            headers=HEADERS,
            head_repo="CivicPatch/j-fork-nonprod",
        )

    payload = client.post.call_args.kwargs["json"]
    assert (payload["head_repo"], payload["maintainer_can_modify"]) == ("CivicPatch/j-fork-nonprod", False)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_labelled_pr_stays_open():
    (number, _), mock_close = await _open(labels_applied=True)

    assert number == 5
    mock_close.assert_not_awaited()
