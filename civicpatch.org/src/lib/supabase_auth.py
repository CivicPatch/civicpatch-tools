from typing import Optional

from fastapi import Request
from pydantic import BaseModel
from supabase import AsyncClient, acreate_client

import environment


class SupabaseUser(BaseModel):
    id: str
    email: Optional[str]
    display_name: Optional[str]

    @property
    def provider(self) -> str:
        return "supabase"


async def create_supabase_client() -> AsyncClient:
    """Constructed once at app startup (FastAPI lifespan) and stored on app.state."""
    env = environment.get_env_vars()
    return await acreate_client(env["SUPABASE_URL"], env["SUPABASE_SECRET_KEY"])


def get_supabase_client(request: Request) -> AsyncClient:
    """FastAPI dependency: returns the app-scoped Supabase client from app.state."""
    return request.app.state.supabase


async def verify_jwt(client: AsyncClient, access_token: str) -> SupabaseUser:
    response = await client.auth.get_user(access_token)
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
