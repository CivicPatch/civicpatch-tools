import secrets
from typing import List, Optional, cast

from database.database import get_pool
from environment import get_env_vars
from schemas.requests import ServerDetail
import lib.hash as hash_utils


async def create_update_user(provider, provider_user_id, email, teams: List[str], display_name: str | None = None):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (provider, provider_user_id, email, display_name)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (provider, provider_user_id)
            DO UPDATE SET email = EXCLUDED.email, display_name = EXCLUDED.display_name
            """,
            (provider, provider_user_id, email, display_name),
        )
        await cur.execute(
            """
            DELETE FROM user_roles
            WHERE provider = %s AND provider_user_id = %s
            """,
            (provider, provider_user_id),
        )
        await cur.executemany(
            """
            INSERT INTO user_roles (provider, provider_user_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, provider_user_id, role)
            DO NOTHING
            """,
            [(provider, provider_user_id, team) for team in teams],
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
            INSERT INTO api_keys (provider, provider_user_id, api_key_hash, api_key_suffix)
            VALUES (%s, %s, %s, %s)
            """,
            (provider, provider_user_id, api_key_hash, api_key_suffix),
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
            SELECT id, api_key_suffix, created_at, revoked_at FROM api_keys
            WHERE provider_user_id = %s AND provider = %s
            """,
            (provider_user_id, provider),
        )
        rows = await cur.fetchall()
    return [
        {"id": r[0], "suffix": r[1], "created_at": r[2], "revoked_at": r[3]}
        for r in rows
    ]


async def get_user(provider, provider_user_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                u.id,
                u.email,
                u.server_url,
                u.created_at,
                ARRAY_REMOVE(ARRAY_AGG(r.role), NULL) AS roles,
                u.display_name
            FROM users u
            LEFT JOIN user_roles r
                ON u.provider = r.provider AND u.provider_user_id = r.provider_user_id
            WHERE u.provider_user_id = %s AND u.provider = %s
            GROUP BY u.id, u.email, u.server_url, u.created_at, u.display_name
            """,
            (provider_user_id, provider),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "email": row[1],
        "server_url": row[2],
        "created_at": row[3],
        "teams": row[4],
        "display_name": row[5],
    }


async def get_user_by_api_key_id(api_key_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        result = await conn.execute(
            """
            SELECT u.provider, u.provider_user_id
            FROM users u
            JOIN api_keys k ON u.provider = k.provider AND u.provider_user_id = k.provider_user_id
            LEFT JOIN user_roles r ON u.provider = r.provider AND u.provider_user_id = r.provider_user_id
            WHERE k.id = %s AND k.revoked_at IS NULL
            GROUP BY u.provider, u.provider_user_id, u.email, u.server_url, u.created_at
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
                u.id,
                u.provider,
                u.provider_user_id,
                u.email,
                u.server_url,
                u.created_at,
                ARRAY_REMOVE(ARRAY_AGG(r.role), NULL) AS roles
            FROM users u
            JOIN api_keys k ON u.provider = k.provider AND u.provider_user_id = k.provider_user_id
            LEFT JOIN user_roles r ON u.provider = r.provider AND u.provider_user_id = r.provider_user_id
            WHERE k.api_key_hash = %s AND k.revoked_at IS NULL
            GROUP BY u.id, u.provider, u.provider_user_id, u.email, u.server_url, u.created_at
            """,
            (candidate_api_key_hash,),
        )
        row = await cur.fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "provider": row[1],
        "provider_user_id": row[2],
        "email": row[3],
        "server_url": row[4],
        "created_at": row[5],
        "teams": row[6],
    }


async def get_user_details(provider, provider_user_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT server_url, email FROM users WHERE provider_user_id = %s AND provider = %s",
            (provider_user_id, provider),
        )
        row = await cur.fetchone()
    if row:
        return {"server_url": row[0], "user_email": row[1]}
    return None


async def get_server_detail_by_active_api_key(api_key) -> Optional[ServerDetail]:
    pool = await get_pool()
    env = get_env_vars()
    candidate_api_key_hash = hash_utils.hash_string(api_key, cast(str, env["DATABASE_HASH_KEY"]))
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT u.email, u.server_url
            FROM users u
            JOIN api_keys k ON u.provider = k.provider AND u.provider_user_id = k.provider_user_id
            WHERE k.api_key_hash = %s AND k.revoked_at IS NULL
            """,
            (candidate_api_key_hash,),
        )
        row = await cur.fetchone()
    if row:
        return ServerDetail(user_email=row[0], server_url=row[1])
    return None


async def update_user_detail(server_url, user_provider, user_provider_id):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE users SET server_url = %s
            WHERE provider = %s AND provider_user_id = %s
            """,
            (server_url, user_provider, user_provider_id),
        )


async def get_user_id_by_provider(provider: str, provider_user_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM users WHERE provider = %s AND provider_user_id = %s",
            (provider, provider_user_id),
        )
        row = await cur.fetchone()
    return str(row[0]) if row else None


async def get_api_usage_for_user(provider: str, provider_user_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT
                ul.daily_limit,
                COUNT(r.id) AS usage_count
            FROM api_usage_limits ul
            LEFT JOIN users u ON u.provider = ul.provider AND u.provider_user_id = ul.provider_user_id
            LEFT JOIN requests r ON r.requested_by_user_id = u.id
                AND r.created_at >= NOW() - INTERVAL '24 hours'
            WHERE ul.provider = %s AND ul.provider_user_id = %s
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
            INSERT INTO api_usage_limits (provider, provider_user_id, daily_limit)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, provider_user_id)
            DO UPDATE SET daily_limit = EXCLUDED.daily_limit;
            """,
            (provider, provider_user_id, daily_limit),
        )
