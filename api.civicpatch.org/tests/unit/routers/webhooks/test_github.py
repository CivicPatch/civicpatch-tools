import hashlib
import hmac

import pytest

from routers.webhooks.github import _parse_pr_status, _verify_signature

VALID_BRANCH = "2025-09-25-1a2b__state_wa__place_seattle__government"
REQUEST_ID = "2025-09-25-1a2b"
JURISDICTION_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
MERGED_AT = "2025-09-26T12:00:00Z"


def _make_payload(action, merged=False, merged_at=None, branch=VALID_BRANCH):
    return {
        "action": action,
        "pull_request": {
            "head": {"ref": branch},
            "merged": merged,
            "merged_at": merged_at,
        },
    }


# ── _parse_pr_status ──────────────────────────────────────────────────────────

def test_parse_opened():
    result = _parse_pr_status(_make_payload("opened"))
    assert result == (REQUEST_ID, JURISDICTION_OCDID, "open", None, None)


def test_parse_reopened():
    result = _parse_pr_status(_make_payload("reopened"))
    assert result == (REQUEST_ID, JURISDICTION_OCDID, "open", None, None)


def test_parse_closed_not_merged():
    result = _parse_pr_status(_make_payload("closed", merged=False))
    assert result == (REQUEST_ID, JURISDICTION_OCDID, "closed", None, None)


def test_parse_closed_merged():
    result = _parse_pr_status(_make_payload("closed", merged=True, merged_at=MERGED_AT))
    assert result == (REQUEST_ID, JURISDICTION_OCDID, "merged", MERGED_AT, None)


def test_parse_ignored_action_returns_none():
    assert _parse_pr_status(_make_payload("labeled")) is None


def test_parse_invalid_branch_returns_none():
    payload = _make_payload("opened", branch="not-a-valid-branch")
    assert _parse_pr_status(payload) is None


# ── _verify_signature ─────────────────────────────────────────────────────────

def _make_signature(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_valid():
    body = b'{"action": "opened"}'
    secret = "test-secret"
    sig = _make_signature(body, secret)
    assert _verify_signature(body, secret, sig) is True


def test_verify_signature_wrong_secret():
    body = b'{"action": "opened"}'
    sig = _make_signature(body, "correct-secret")
    assert _verify_signature(body, "wrong-secret", sig) is False


def test_verify_signature_tampered_body():
    secret = "test-secret"
    sig = _make_signature(b"original body", secret)
    assert _verify_signature(b"tampered body", secret, sig) is False
