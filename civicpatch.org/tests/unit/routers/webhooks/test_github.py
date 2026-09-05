import hashlib
import hmac

import pytest

from routers.webhooks.github import _verify_signature


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
