import asyncio
from typing import Optional

from pydantic import BaseModel
from supabase import Client, create_client

import environment


class SupabaseUser(BaseModel):
    id: str
    email: Optional[str]
    display_name: Optional[str]

    @property
    def provider(self) -> str:
        return "supabase"


def get_supabase_client() -> Client:
    env = environment.get_env_vars()
    url = env.get("SUPABASE_URL")
    secret_key = env.get("SUPABASE_SECRET_KEY")
    if not url or not secret_key:
        raise ValueError("Supabase auth is not configured")
    return create_client(url, secret_key)


async def verify_jwt(client: Client, access_token: str) -> SupabaseUser:
    response = await asyncio.to_thread(client.auth.get_user, access_token)
    user = getattr(response, "user", None)
    if user is None:
        raise ValueError("Invalid Supabase JWT")

    user_metadata = getattr(user, "user_metadata", {}) or {}
    display_name = (
        user_metadata.get("full_name")
        or user_metadata.get("name")
        or user_metadata.get("display_name")
    )
    return SupabaseUser(
        id=str(user.id),
        email=getattr(user, "email", None),
        display_name=display_name,
    )
