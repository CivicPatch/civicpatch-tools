"""Access tokens from Supabase's OAuth 2.1 server: how an MCP client that signs in (ChatGPT) calls
/mcp. Checked against the project's published signing keys and its issuer."""

import asyncio
from functools import lru_cache

import httpx
import jwt
from jwt import PyJWKClient

from lib.supabase_oauth import TIMEOUT_SECONDS

ALGORITHMS = ["ES256", "RS256"]
# Only the OAuth server puts `client_id` in a token, so a plain Supabase sign-in token is refused here.
REQUIRED_CLAIMS = ["exp", "iss", "sub", "client_id"]

_metadata: dict[str, dict] = {}


class TokenRejected(Exception):
    pass


def looks_like_jwt(token: str) -> bool:
    """Our API keys are url-safe base64 with no dots; a JWT has exactly two."""
    return token.count(".") == 2


@lru_cache(maxsize=4)
def _jwks_client(supabase_url: str) -> PyJWKClient:
    return PyJWKClient(f"{supabase_url}/auth/v1/.well-known/jwks.json")


async def fetch_authorization_server_metadata(supabase_url: str) -> dict:
    """Supabase's OAuth discovery document (RFC 8414), fetched once."""
    if supabase_url not in _metadata:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.get(f"{supabase_url}/auth/v1/.well-known/oauth-authorization-server")
            response.raise_for_status()
            _metadata[supabase_url] = response.json()
    return _metadata[supabase_url]


async def fetch_issuer(supabase_url: str) -> str:
    """The issuer Supabase stamps on its tokens: its public address, which the backend may reach
    by another (supabase_url is internal on dev)."""
    return (await fetch_authorization_server_metadata(supabase_url))["issuer"]


async def verify_supabase_token(token: str, supabase_url: str) -> dict:
    """The token's claims, or TokenRejected."""
    try:
        signing_key = await asyncio.to_thread(_jwks_client(supabase_url).get_signing_key_from_jwt, token)
        issuer = await fetch_issuer(supabase_url)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITHMS,
            issuer=issuer,
            options={"require": REQUIRED_CLAIMS, "verify_aud": False},
        )
    except jwt.PyJWTError as error:
        raise TokenRejected(str(error)) from error
