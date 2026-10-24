"""Supabase's auth API for OAuth apps: a one-off Supabase session for a user our own cookie already
vouches for, then an authorization read and decided, or the user's approved apps listed and revoked,
with it. Plain HTTP, so no shared client's headers change."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx

TIMEOUT_SECONDS = 10
APPROVE = "approve"
DENY = "deny"


class SupabaseAuthError(Exception):
    def __init__(self, message: str, status: int):
        super().__init__(message)
        self.status = status


def _error_message(response: httpx.Response) -> str:
    # Most errors are JSON with a `msg`; a disabled endpoint is a plain-text "404 page not found".
    try:
        return response.json().get("msg") or response.reason_phrase
    except ValueError:
        return response.text or response.reason_phrase


async def _call(
    method: str, url: str, secret_key: str, body: dict | None, access_token: str | None, params: dict | None = None
) -> Any:
    headers = {"apikey": secret_key, "Authorization": f"Bearer {access_token or secret_key}"}
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.request(method, url, headers=headers, json=body, params=params)
    if response.is_error:
        raise SupabaseAuthError(_error_message(response), response.status_code)
    return response.json() if response.content else {}


async def open_session(supabase_url: str, secret_key: str, supabase_user_id: str) -> str:
    """An access token for the user, minted with the admin API: a magic link, sent nowhere, verified at once."""
    user = await _call("GET", f"{supabase_url}/auth/v1/admin/users/{supabase_user_id}", secret_key, None, None)
    link_body = {"type": "magiclink", "email": user["email"]}
    link = await _call("POST", f"{supabase_url}/auth/v1/admin/generate_link", secret_key, link_body, None)
    verify_body = {"type": "magiclink", "token_hash": link["hashed_token"]}
    session = await _call("POST", f"{supabase_url}/auth/v1/verify", secret_key, verify_body, None)
    return session["access_token"]


async def close_session(supabase_url: str, secret_key: str, access_token: str) -> None:
    # `local`: the default (`global`) would also end the user's other sessions, connected agents' included.
    await _call("POST", f"{supabase_url}/auth/v1/logout?scope=local", secret_key, None, access_token)


@asynccontextmanager
async def user_session(supabase_url: str, secret_key: str, supabase_user_id: str) -> AsyncGenerator[str, None]:
    """The user's one-off access token, closed again however the block ends."""
    access_token = await open_session(supabase_url, secret_key, supabase_user_id)
    try:
        yield access_token
    finally:
        await close_session(supabase_url, secret_key, access_token)


async def list_grants(supabase_url: str, secret_key: str, access_token: str) -> list[dict]:
    """The apps the session's user has approved: each with its client (id, name) and `granted_at`."""
    return await _call("GET", f"{supabase_url}/auth/v1/user/oauth/grants", secret_key, None, access_token)


async def revoke_grant(supabase_url: str, secret_key: str, access_token: str, client_id: str) -> None:
    url = f"{supabase_url}/auth/v1/user/oauth/grants"
    await _call("DELETE", url, secret_key, None, access_token, params={"client_id": client_id})


async def fetch_authorization(supabase_url: str, secret_key: str, authorization_id: str, access_token: str) -> dict:
    """The request's details; for a client the user already approved, Supabase approves it here and
    answers with only the redirect back to the client."""
    url = f"{supabase_url}/auth/v1/oauth/authorizations/{authorization_id}"
    return await _call("GET", url, secret_key, None, access_token)


async def decide_authorization(
    supabase_url: str, secret_key: str, authorization_id: str, access_token: str, action: str
) -> str:
    """Where to send the browser next: back to the client, with a code or the refusal."""
    url = f"{supabase_url}/auth/v1/oauth/authorizations/{authorization_id}/consent"
    decision = await _call("POST", url, secret_key, {"action": action}, access_token)
    return decision.get("redirect_url") or decision["redirect_to"]
