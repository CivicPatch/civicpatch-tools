"""The OAuth token check against a real ES256 key made here; only the network fetches are replaced."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from lib import supabase_tokens
from lib.supabase_tokens import TokenRejected, looks_like_jwt, verify_supabase_token

pytestmark = pytest.mark.unit

_SUPABASE_URL = "http://supabase.test"
_ISSUER = "https://public.test/auth/v1"
_KEY = ec.generate_private_key(ec.SECP256R1())


def _token(key=_KEY, **overrides) -> str:
    claims = {"sub": "sb-user", "iss": _ISSUER, "exp": int(time.time()) + 600, "client_id": "chatgpt", **overrides}
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm="ES256")


def _published(key=_KEY):
    jwks = SimpleNamespace(get_signing_key_from_jwt=lambda _token: SimpleNamespace(key=key.public_key()))
    return (
        patch.object(supabase_tokens, "_jwks_client", lambda _url: jwks),
        patch.object(supabase_tokens, "fetch_issuer", AsyncMock(return_value=_ISSUER)),
    )


@pytest.mark.asyncio
async def test_a_token_signed_by_the_published_key_gives_its_claims():
    keys, issuer = _published()
    with keys, issuer:
        claims = await verify_supabase_token(_token(), _SUPABASE_URL)
    assert (claims["sub"], claims["client_id"]) == ("sb-user", "chatgpt")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "token",
    [
        _token(exp=int(time.time()) - 60),
        _token(iss="https://elsewhere.test/auth/v1"),
        _token(client_id=None),
        _token(key=ec.generate_private_key(ec.SECP256R1())),
    ],
    ids=["expired", "another issuer", "not from the OAuth server", "signed by another key"],
)
async def test_any_other_token_is_rejected(token: str):
    keys, issuer = _published()
    with keys, issuer, pytest.raises(TokenRejected):
        await verify_supabase_token(token, _SUPABASE_URL)


def test_an_api_key_is_not_taken_for_a_token():
    assert looks_like_jwt(_token())
    assert not looks_like_jwt("dGhpcy1pcy1hbi1hcGkta2V5LW5vLWRvdHMtaGVyZQ")
