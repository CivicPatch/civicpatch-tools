import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import pytest

from routers.webhooks.github import (
    _handle_review_issue_pr_event,
    _parse_pr_status,
    _verify_signature,
)

VALID_BRANCH = "job/wa/local/place_seattle/2025-09-25-1a2b"
REQUEST_ID = "2025-09-25-1a2b"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
MERGED_AT = "2025-09-26T12:00:00Z"
ISSUE_ID = "d1af4053-1234-5678-9abc-def012345678"
RESOLVE_BRANCH = f"resolve/role/{ISSUE_ID}"
RESOLVE_PR_URL = "https://github.com/CivicPatch/civicpatch-community/pull/42"


def _make_payload(action, merged=False, merged_at=None, branch=VALID_BRANCH, pr_url=None):
    return {
        "action": action,
        "pull_request": {
            "head": {"ref": branch},
            "html_url": pr_url,
            "merged": merged,
            "merged_at": merged_at,
        },
    }


# ── _parse_pr_status ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_parse_opened():
    result = _parse_pr_status(_make_payload("opened"))
    assert result == (REQUEST_ID, "open", None, None)


@pytest.mark.unit
def test_parse_reopened():
    result = _parse_pr_status(_make_payload("reopened"))
    assert result == (REQUEST_ID, "open", None, None)


@pytest.mark.unit
def test_parse_closed_not_merged():
    result = _parse_pr_status(_make_payload("closed", merged=False))
    assert result == (REQUEST_ID, "closed", None, None)


@pytest.mark.unit
def test_parse_closed_merged():
    result = _parse_pr_status(_make_payload("closed", merged=True, merged_at=MERGED_AT))
    assert result == (REQUEST_ID, "merged", MERGED_AT, None)


@pytest.mark.unit
def test_parse_ignored_action_returns_none():
    assert _parse_pr_status(_make_payload("labeled")) is None


@pytest.mark.unit
def test_parse_invalid_branch_returns_none():
    payload = _make_payload("opened", branch="not-a-valid-branch")
    assert _parse_pr_status(payload) is None


# ── _handle_review_issue_pr_event ─────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_review_issue_pr_merged_resolves_issue():
    payload = _make_payload("closed", merged=True, branch=RESOLVE_BRANCH, pr_url=RESOLVE_PR_URL)
    with (
        patch(
            "routers.webhooks.github.issues_db.get_issue_by_pull_request_url",
            new_callable=AsyncMock,
            return_value={"id": ISSUE_ID, "status": "pr_opened"},
        ),
        patch(
            "routers.webhooks.github.issues_db.resolve_issue",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "routers.webhooks.github.issues_db.reopen_issue",
            new_callable=AsyncMock,
        ) as mock_reopen,
    ):
        await _handle_review_issue_pr_event(payload)
        mock_resolve.assert_called_once_with(ISSUE_ID)
        mock_reopen.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_review_issue_pr_closed_without_merge_reopens_issue():
    payload = _make_payload("closed", merged=False, branch=RESOLVE_BRANCH, pr_url=RESOLVE_PR_URL)
    with (
        patch(
            "routers.webhooks.github.issues_db.get_issue_by_pull_request_url",
            new_callable=AsyncMock,
            return_value={"id": ISSUE_ID, "status": "pr_opened"},
        ),
        patch(
            "routers.webhooks.github.issues_db.resolve_issue",
            new_callable=AsyncMock,
        ) as mock_resolve,
        patch(
            "routers.webhooks.github.issues_db.reopen_issue",
            new_callable=AsyncMock,
        ) as mock_reopen,
    ):
        await _handle_review_issue_pr_event(payload)
        mock_reopen.assert_called_once_with(ISSUE_ID)
        mock_resolve.assert_not_called()


# ── _verify_signature ─────────────────────────────────────────────────────────

def _make_signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.unit
def test_verify_signature_valid():
    body = b'{"action": "opened"}'
    secret = "test-secret"
    sig = _make_signature(body, secret)
    assert _verify_signature(body, secret, sig) is True


@pytest.mark.unit
def test_verify_signature_wrong_secret():
    body = b'{"action": "opened"}'
    sig = _make_signature(body, "correct-secret")
    assert _verify_signature(body, "wrong-secret", sig) is False


@pytest.mark.unit
def test_verify_signature_tampered_body():
    secret = "test-secret"
    sig = _make_signature(b"original body", secret)
    assert _verify_signature(b"tampered body", secret, sig) is False
