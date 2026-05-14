import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.blog_sync import SyncCollisionError, SyncResult
from routers.webhooks.blog_sync import _verify_signature, get_router

SECRET = "test-blog_sync_webhook_secret"


WEBHOOK_PATH = "/webhooks/blog-sync"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(get_router(), prefix=WEBHOOK_PATH)
    return TestClient(app)


def _sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _payload(discussions: list | None = None) -> bytes:
    return json.dumps({"discussions": discussions or []}).encode()


# ── _verify_signature ─────────────────────────────────────────────────────────

@pytest.mark.unit
def test_verify_signature_matches():
    body = b'{"discussions": []}'
    sig = _sign(body)
    assert _verify_signature(body, SECRET, sig) is True


@pytest.mark.unit
def test_verify_signature_rejects_wrong_secret():
    body = b'{"discussions": []}'
    sig = _sign(body, secret="wrong")
    assert _verify_signature(body, SECRET, sig) is False


@pytest.mark.unit
def test_verify_signature_rejects_tampered_body():
    sig = _sign(b'{"discussions": []}')
    assert _verify_signature(b'{"discussions": [1]}', SECRET, sig) is False


# ── webhook endpoint ──────────────────────────────────────────────────────────

@pytest.mark.unit
def test_happy_path_returns_synced_list(client, mocker):
    mocker.patch(
        "routers.webhooks.blog_sync.sync_blog_posts",
        new=mocker.AsyncMock(return_value=SyncResult(synced=["a", "b"], skipped=[])),
    )
    body = _payload()
    resp = client.post(WEBHOOK_PATH, content=body, headers={"x-signature-sha256": _sign(body)})
    assert resp.status_code == 200
    assert resp.json() == {"synced": ["a", "b"]}


@pytest.mark.unit
def test_missing_secret_returns_503(client, monkeypatch):
    monkeypatch.setattr(
        "routers.webhooks.blog_sync.get_env_vars",
        lambda: {"BLOG_SYNC_WEBHOOK_SECRET": None},
    )
    body = _payload()
    resp = client.post(WEBHOOK_PATH, content=body, headers={"x-signature-sha256": _sign(body)})
    assert resp.status_code == 503


@pytest.mark.unit
def test_invalid_signature_returns_401(client):
    body = _payload()
    resp = client.post(
        WEBHOOK_PATH, content=body, headers={"x-signature-sha256": "sha256=deadbeef"}
    )
    assert resp.status_code == 401


@pytest.mark.unit
def test_invalid_payload_schema_returns_422(client):
    body = b'{"not_discussions": []}'
    resp = client.post(WEBHOOK_PATH, content=body, headers={"x-signature-sha256": _sign(body)})
    assert resp.status_code == 422


@pytest.mark.unit
def test_slug_collision_returns_500_with_detail(client, mocker):
    mocker.patch(
        "routers.webhooks.blog_sync.sync_blog_posts",
        new=mocker.AsyncMock(side_effect=SyncCollisionError("volunteer", [1, 2])),
    )
    body = _payload()
    resp = client.post(WEBHOOK_PATH, content=body, headers={"x-signature-sha256": _sign(body)})
    assert resp.status_code == 500
    assert resp.json()["detail"]["error"] == "slug_collision"
    assert resp.json()["detail"]["slug"] == "volunteer"
    assert resp.json()["detail"]["discussion_numbers"] == [1, 2]


@pytest.mark.unit
def test_partial_sync_returns_500_with_detail(client, mocker):
    mocker.patch(
        "routers.webhooks.blog_sync.sync_blog_posts",
        new=mocker.AsyncMock(
            return_value=SyncResult(synced=["a"], skipped=[(7, "no frontmatter")])
        ),
    )
    body = _payload()
    resp = client.post(WEBHOOK_PATH, content=body, headers={"x-signature-sha256": _sign(body)})
    assert resp.status_code == 500
    assert resp.json()["detail"]["error"] == "partial_sync"
    assert resp.json()["detail"]["synced"] == ["a"]
