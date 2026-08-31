from typing import Optional

import environment
from fastapi import Request
from pydantic import BaseModel
from supabase import AsyncClient, acreate_client


class SupabaseUser(BaseModel):
    id: str
    email: Optional[str]
    display_name: Optional[str]

    @property
    def provider(self) -> str:
        return "supabase"


async def create_supabase_client() -> AsyncClient:
    """User-facing client. Constructed once at app startup (FastAPI lifespan)
    and stored on app.state.supabase. Mutated by user sign-in flows (verify_otp
    etc.) — its Authorization header gets overwritten to the signed-in user's
    JWT, so it must not be used for auth.admin.* calls."""
    env = environment.get_env_vars()
    return await acreate_client(env["SUPABASE_URL"], env["SUPABASE_SECRET_KEY"])


async def create_supabase_admin_client() -> AsyncClient:
    """Admin client. Constructed once at app startup and stored on
    app.state.supabase_admin. Same secret key as the user-facing client, but
    held separately so user sign-in flows don't mutate its Authorization
    header. Use for auth.admin.* calls only — never pass this to verify_otp
    or any user-auth flow.

    Upstream issue: https://github.com/supabase/supabase-py/issues/1143
    (apikey/Authorization header drift after sign-in on a shared server client).
    The admin namespace shares the main client's _headers dict by reference
    (supabase/_async/client.py:347 in supabase-py 2.30), so isolating the
    admin client is the workaround until the SDK provides a stateless option."""
    env = environment.get_env_vars()
    return await acreate_client(env["SUPABASE_URL"], env["SUPABASE_SECRET_KEY"])


def get_supabase_client(request: Request) -> AsyncClient:
    """FastAPI dependency: app-scoped user-facing Supabase client. Mutated by
    sign-in flows — see create_supabase_client. Do not use for admin calls."""
    return request.app.state.supabase


def get_supabase_admin_client(request: Request) -> AsyncClient:
    """FastAPI dependency: app-scoped admin Supabase client, isolated from
    user sign-in flows. See create_supabase_admin_client."""
    return request.app.state.supabase_admin


def to_supabase_user(user_obj) -> SupabaseUser:
    """Build a typed SupabaseUser from a supabase-py user object."""
    user_metadata = getattr(user_obj, "user_metadata", {}) or {}
    display_name = (
        user_metadata.get("full_name")
        or user_metadata.get("name")
        or user_metadata.get("display_name")
    )
    return SupabaseUser(
        id=str(user_obj.id),
        email=getattr(user_obj, "email", None),
        display_name=display_name,
    )
