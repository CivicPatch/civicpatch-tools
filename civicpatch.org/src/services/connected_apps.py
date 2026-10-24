"""OAuth apps and the user's approvals of them, read and changed through a one-off Supabase session for the user."""

from http import HTTPStatus

from lib.supabase_oauth import SupabaseAuthError, decide_authorization, fetch_authorization, list_grants, revoke_grant, user_session
from schemas.connected_apps import ConnectedApp


def to_connected_app(grant: dict) -> ConnectedApp:
    return ConnectedApp(client_id=grant["client"]["id"], name=grant["client"]["name"], granted_at=grant["granted_at"])


async def fetch_authorization_request(supabase_url: str, secret_key: str, supabase_user_id: str, authorization_id: str) -> dict:
    async with user_session(supabase_url, secret_key, supabase_user_id) as access_token:
        return await fetch_authorization(supabase_url, secret_key, authorization_id, access_token)


async def decide_authorization_request(
    supabase_url: str, secret_key: str, supabase_user_id: str, authorization_id: str, action: str
) -> str:
    async with user_session(supabase_url, secret_key, supabase_user_id) as access_token:
        return await decide_authorization(supabase_url, secret_key, authorization_id, access_token, action)


async def fetch_connected_apps(supabase_url: str, secret_key: str, supabase_user_id: str) -> list[ConnectedApp]:
    async with user_session(supabase_url, secret_key, supabase_user_id) as access_token:
        try:
            grants = await list_grants(supabase_url, secret_key, access_token)
        except SupabaseAuthError as error:
            # Supabase's OAuth server is off (local dev without it): nothing can have been approved.
            if error.status == HTTPStatus.NOT_FOUND:
                return []
            raise
    return [to_connected_app(grant) for grant in grants]


async def disconnect_app(supabase_url: str, secret_key: str, supabase_user_id: str, client_id: str) -> None:
    async with user_session(supabase_url, secret_key, supabase_user_id) as access_token:
        await revoke_grant(supabase_url, secret_key, access_token, client_id)
