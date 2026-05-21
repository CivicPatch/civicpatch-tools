import secrets
from typing import cast

from database.database import get_pool
from environment import get_env_vars
import lib.hash as hash_utils


async def upsert_user(provider, provider_user_id, email, display_name: str | None = None) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (provider, provider_user_id, email, display_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (provider, provider_user_id)
            DO UPDATE SET email = EXCLUDED.email, display_name = EXCLUDED.display_name
            RETURNING id::text
            """,
            (provider, provider_user_id, email, display_name),
        )
        row = await cur.fetchone()
    assert row, "upsert_user RETURNING returned no row"
    return cast(str, row[0])


async def set_user_roles(user_id: str, roles: list[str]) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM user_roles WHERE user_id = %s",
            (user_id,),
        )
        if roles:
            await conn.execute(
                """
                INSERT INTO user_roles (user_id, role)
                SELECT %s::uuid, UNNEST(%s::text[])
                """,
                (user_id, roles),
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


async def list_users_with_roles(limit: int = 100, offset: int = 0) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                u.id::text,
                u.email,
                u.display_name,
                u.provider,
                u.provider_user_id,
                ARRAY_REMOVE(ARRAY_AGG(r.role), NULL) AS roles
            FROM users u
            LEFT JOIN user_roles r ON r.user_id = u.id
            GROUP BY u.id, u.email, u.display_name, u.provider, u.provider_user_id, u.created_at
            ORDER BY u.created_at ASC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = await cur.fetchall()
    return [
        {
            "id": r[0],
            "email": r[1],
            "display_name": r[2],
            "provider": r[3],
            "provider_user_id": r[4],
            "roles": r[5],
        }
        for r in rows
    ]


async def get_user(provider, provider_user_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                u.id::text,
                u.email,
                u.created_at,
                ARRAY_REMOVE(ARRAY_AGG(r.role), NULL) AS roles,
                u.display_name
            FROM users u
            LEFT JOIN user_roles r ON r.user_id = u.id
            WHERE u.provider_user_id = %s AND u.provider = %s
            GROUP BY u.id, u.email, u.created_at, u.display_name
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
        "teams": row[3],
        "display_name": row[4],
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
            SELECT
                u.id::text,
                u.provider,
                u.provider_user_id,
                u.email,
                u.created_at,
                ARRAY_REMOVE(ARRAY_AGG(r.role), NULL) AS roles
            FROM users u
            JOIN api_keys k ON u.id = k.user_id
            LEFT JOIN user_roles r ON r.user_id = u.id
            WHERE k.api_key_hash = %s AND k.revoked_at IS NULL
            GROUP BY u.id, u.provider, u.provider_user_id, u.email, u.created_at
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
        "teams": row[5],
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
            SELECT id::text, provider, provider_user_id, email, display_name
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
        "display_name": row[4],
    }


async def get_api_usage_for_user(provider: str, provider_user_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                ul.daily_limit,
                COUNT(r.id) AS usage_count
            FROM api_usage_limits ul
            JOIN users u ON u.id = ul.user_id
            LEFT JOIN requests r ON r.requested_by_user_id = u.id
                AND r.created_at >= NOW() - INTERVAL '24 hours'
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
