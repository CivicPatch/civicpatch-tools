from unittest.mock import AsyncMock, patch

import pytest

from services.review_issue_report import (
    GithubIssueCreationError,
    ReviewNotFoundError,
    report_review_issue,
)

CHANGESET_ID = "req-1"

REVIEW = {
    "changeset_id": CHANGESET_ID,
    "jurisdiction": {"ocdid": "ocd-jurisdiction/x", "name": "Oakland", "path": "ca/local/oakland"},
    "pr": {"url": "https://github.com/org/open-data/pull/42", "status": "open", "number": 42},
}

REVIEW_WITHOUT_PR_URL = {
    **REVIEW,
    "pr": {"url": None, "status": "DEFAULT", "number": None},
}


def _patches(review=REVIEW, github_result=(9, "https://github.com/org/open-data/issues/9"), issue_id="issue-1"):
    return (
        patch(
            "services.review_issue_report.pull_requests_db.get_pull_request_for_review",
            new_callable=AsyncMock, return_value=review,
        ),
        patch(
            "services.review_issue_report.github_service.create_issue",
            new_callable=AsyncMock, return_value=github_result,
        ),
        patch(
            "services.review_issue_report.issues_db.create_user_reported_issue",
            new_callable=AsyncMock, return_value=issue_id,
        ),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_report_review_issue_files_github_issue_and_records_db_row():
    review_p, github_p, db_p = _patches()
    with review_p, github_p as mock_create_issue, db_p as mock_db_insert:
        result = await report_review_issue(CHANGESET_ID, "Something looks wrong.", "user-1", "Jane Reviewer")

    assert result == {
        "id": "issue-1",
        "github_issue_url": "https://github.com/org/open-data/issues/9",
        "github_issue_number": 9,
    }

    mock_create_issue.assert_awaited_once()
    _, kwargs = mock_create_issue.call_args
    assert kwargs["title"] == "Review flag: Oakland"
    assert "Something looks wrong." in kwargs["body"]
    assert "Reported by Jane Reviewer." in kwargs["body"]
    assert "state=ca&changeset_id=req-1" in kwargs["body"]
    assert "https://github.com/org/open-data/pull/42" in kwargs["body"]
    assert kwargs["labels"] == ["user-reported"]

    mock_db_insert.assert_awaited_once()
    _, db_kwargs = mock_db_insert.call_args
    assert db_kwargs["changeset_id"] == CHANGESET_ID
    assert db_kwargs["github_issue_url"] == "https://github.com/org/open-data/issues/9"
    assert db_kwargs["github_issue_number"] == 9
    assert db_kwargs["reported_by_user_id"] == "user-1"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_report_review_issue_omits_pr_line_when_no_pr_url():
    review_p, github_p, db_p = _patches(review=REVIEW_WITHOUT_PR_URL)
    with review_p, github_p as mock_create_issue, db_p:
        await report_review_issue(CHANGESET_ID, "Something looks wrong.", "user-1", "Jane Reviewer")

    _, kwargs = mock_create_issue.call_args
    assert "Reviewing" not in kwargs["body"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_report_review_issue_raises_when_review_not_found():
    with patch(
        "services.review_issue_report.pull_requests_db.get_pull_request_for_review",
        new_callable=AsyncMock, return_value=None,
    ):
        with pytest.raises(ReviewNotFoundError):
            await report_review_issue(CHANGESET_ID, "desc", "user-1", "Jane Reviewer")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_report_review_issue_raises_and_skips_db_write_when_github_fails():
    review_p, github_p, db_p = _patches(github_result=(None, "GitHub is down"))
    with review_p, github_p, db_p as mock_db_insert:
        with pytest.raises(GithubIssueCreationError):
            await report_review_issue(CHANGESET_ID, "desc", "user-1", "Jane Reviewer")

    mock_db_insert.assert_not_awaited()
