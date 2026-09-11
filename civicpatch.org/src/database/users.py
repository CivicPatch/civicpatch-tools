import secrets
import uuid
from typing import cast

from database.database import get_pool

# The actor for anything no person did — a supersede sweep, an auto-publish, a backfill.
# Seeded by migration 160. Nothing can log in as it: `create_user` is the auth path's only
# writer and always passes provider 'supabase', so 'system' is unreachable there.
SYSTEM_USER_ID = "00000000-0000-4000-8000-000000000001"
from environment import get_env_vars
import lib.hash as hash_utils


async def create_user(provider, provider_user_id, email) -> str:
    # A brand-new sign-in has no chosen name yet. Migration 192 established that this column
    # is never NULL — a user who hasn't picked one gets their own id as a placeholder, same
    # shape as every other value in the column. `username == id` is exactly the signal
    # `routers.frontend.needs_username` uses to route them to `/login/username`.
    user_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (id, provider, provider_user_id, email, username, last_login_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id::text
            """,
            (user_id, provider, provider_user_id, email, user_id),
        )
        row = await cur.fetchone()
    assert row, "create_user RETURNING returned no row"
    return cast(str, row[0])


async def touch_last_login(provider, provider_user_id, email) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE users SET email = %s, last_login_at = NOW()
            WHERE provider = %s AND provider_user_id = %s
            """,
            (email, provider, provider_user_id),
        )


async def set_user_role(user_id: str, role: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE users SET role = %s WHERE id = %s",
            (role, user_id),
        )


async def set_username(user_id: str, username: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE users SET username = %s WHERE id = %s",
            (username, user_id),
        )


async def create_api_key(provider, provider_user_id):
    pool = await get_pool()
    env = get_env_vars()
    api_key = secrets.token_urlsafe(32)
    api_key_hash = hash_utils.hash_string(api_key, cast(str, env["DATABASE_HASH_KEY"]))
    api_key_suffix = api_key[-4:]
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO api_keys (user_id, api_key_hash, api_key_suffix)
            SELECT id, %s, %s FROM users WHERE provider = %s AND provider_user_id = %s
            """,
            (api_key_hash, api_key_suffix, provider, provider_user_id),
        )
    return api_key


async def revoke_api_key(api_key_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP WHERE id = %s",
            (api_key_id,),
        )


async def delete_api_key(api_key_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM api_keys WHERE id = %s",
            (api_key_id,),
        )


async def get_api_keys_for_user(provider, provider_user_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT k.id, k.api_key_suffix, k.created_at, k.revoked_at
            FROM api_keys k
            JOIN users u ON u.id = k.user_id
            WHERE u.provider = %s AND u.provider_user_id = %s
            """,
            (provider, provider_user_id),
        )
        rows = await cur.fetchall()
    return [
        {"id": r[0], "suffix": r[1], "created_at": r[2], "revoked_at": r[3]}
        for r in rows
    ]


async def list_users(limit: int = 100, offset: int = 0) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, email, username, provider, provider_user_id, role, last_login_at
            FROM users
            ORDER BY created_at ASC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "email": r[1],
            "username": r[2],
            "provider": r[3],
            "provider_user_id": r[4],
            "role": r[5],
            "last_login_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


async def get_user(provider, provider_user_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, email, created_at, role, username
            FROM users
            WHERE provider_user_id = %s AND provider = %s
            """,
            (provider_user_id, provider),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "email": row[1],
        "created_at": row[2],
        "role": row[3],
        "username": row[4],
    }


async def get_user_by_api_key_id(api_key_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT u.provider, u.provider_user_id
            FROM users u
            JOIN api_keys k ON u.id = k.user_id
            WHERE k.id = %s AND k.revoked_at IS NULL
            """,
            (api_key_id,),
        )
        row = await result.fetchone()
    if not row:
        return None
    return {"provider": row[0], "provider_user_id": row[1]}


async def get_user_by_api_key(api_key):
    pool = await get_pool()
    env = get_env_vars()
    candidate_api_key_hash = hash_utils.hash_string(api_key, cast(str, env["DATABASE_HASH_KEY"]))
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT u.id::text, u.provider, u.provider_user_id, u.email, u.created_at, u.role
            FROM users u
            JOIN api_keys k ON u.id = k.user_id
            WHERE k.api_key_hash = %s AND k.revoked_at IS NULL
            """,
            (candidate_api_key_hash,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "provider": row[1],
        "provider_user_id": row[2],
        "email": row[3],
        "created_at": row[4],
        "role": row[5],
    }



async def get_user_id_by_provider(provider: str, provider_user_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM users WHERE provider = %s AND provider_user_id = %s",
            (provider, provider_user_id),
        )
        row = await cur.fetchone()
    return cast(str, row[0]) if row else None


async def get_user_by_id(user_id: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, provider, provider_user_id, email, username, role, last_login_at
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "provider": row[1],
        "provider_user_id": row[2],
        "email": row[3],
        "username": row[4],
        "role": row[5],
        "last_login_at": row[6].isoformat() if row[6] else None,
    }


async def get_user_by_username(username: str) -> dict | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id::text, provider, provider_user_id, email, username, role, last_login_at
            FROM users
            WHERE username = %s
            """,
            (username,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "provider": row[1],
        "provider_user_id": row[2],
        "email": row[3],
        "username": row[4],
        "role": row[5],
        "last_login_at": row[6].isoformat() if row[6] else None,
    }


async def get_api_usage_for_user(provider: str, provider_user_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                ul.daily_limit,
                COUNT(changesets.id) AS usage_count
            FROM api_usage_limits ul
            JOIN users u ON u.id = ul.user_id
            LEFT JOIN changesets ON changesets.created_by_user_id = u.id
                AND changesets.created_at >= NOW() - INTERVAL '24 hours'
            WHERE u.provider = %s AND u.provider_user_id = %s
            GROUP BY ul.daily_limit;
            """,
            (provider, provider_user_id),
        )
        row = await cur.fetchone()
    if row:
        return {"daily_limit": row[0], "usage_count": row[1]}
    return {"daily_limit": 0, "usage_count": 0}


async def set_daily_limit_for_user(provider: str, provider_user_id: str, daily_limit: int = 100):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO api_usage_limits (user_id, daily_limit)
            SELECT id, %s FROM users WHERE provider = %s AND provider_user_id = %s
            ON CONFLICT (user_id)
            DO UPDATE SET daily_limit = EXCLUDED.daily_limit;
            """,
            (daily_limit, provider, provider_user_id),
        )
