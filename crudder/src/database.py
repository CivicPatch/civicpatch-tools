import hashlib
import hmac
import os
from typing import List

from psycopg_pool import AsyncConnectionPool

from schemas import Person

CRUDDER_DB_URL = os.getenv("CRUDDER_DB_URL")
DATABASE_HASH_KEY = os.getenv("DATABASE_HASH_KEY")

pool = AsyncConnectionPool(CRUDDER_DB_URL, open=False)


def hash_string(string: str, hash_key: str) -> str:
    return hmac.new(hash_key.encode(), string.encode(), hashlib.sha512).hexdigest()


async def maybe_insert_user(provider, provider_user_id, email):
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO users (provider, provider_user_id, email)
            VALUES (%s, %s, %s)
            ON CONFLICT (provider, provider_user_id) DO UPDATE
            SET email = EXCLUDED.email
        """,
            (provider, provider_user_id, email),
        )


async def create_api_key(provider, provider_user_id, database_hash_key):
    import secrets

    api_key = secrets.token_urlsafe(32)
    # Hash the API key before storing
    api_key_hash = hash_string(api_key, database_hash_key)
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
    async with pool.connection() as conn:
        await conn.execute(
            """
        UPDATE api_keys SET revoked_at = CURRENT_TIMESTAMP
        WHERE id = %s
    """,
            (api_key_id,),
        )


async def get_api_keys_for_user(provider, provider_user_id):
    data = []
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
        SELECT id, api_key_suffix, created_at, revoked_at FROM api_keys
        WHERE provider_user_id = %s AND provider = %s
    """,
            (provider_user_id, provider),
        )
        rows = await cur.fetchall()

        for row in rows:
            data.append(
                {
                    "id": row[0],
                    "suffix": row[1],
                    "created_at": row[2],
                    "revoked_at": row[3],
                }
            )
    return data


async def get_user_details(provider, provider_user_id):
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
        SELECT server_url, email FROM users
        WHERE provider_user_id = %s AND provider = %s
    """,
            (provider_user_id, provider),
        )
        row = await cur.fetchone()
    if row:
        return {
            "server_url": row[0],
            "user_email": row[1],
        }
    return None


async def user_is_approved(user_provider, provider_user_id) -> bool:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM users
                WHERE provider = %s
                  AND provider_user_id = %s
                  AND is_approved = TRUE
            ) AS is_user_approved;
            """,
            (user_provider, provider_user_id),
        )
        row = await cur.fetchone()
        return row[0] if row else False


async def is_active_api_key(database_hash_key, api_key) -> bool:
    candidate_api_key = api_key.strip()
    candidate_api_key_hash = hash_string(candidate_api_key, database_hash_key)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
        SELECT ak.id
        FROM api_keys ak
        JOIN users u
        ON ak.provider = u.provider
        AND ak.provider_user_id = u.provider_user_id
        WHERE ak.api_key_hash = %s
        AND ak.revoked_at IS NULL
        AND u.is_approved = TRUE;
    """,
            (candidate_api_key_hash),
        )
        row = await cur.fetchone()
    return row is not None


async def get_server_detail_by_active_api_key(api_key):
    candidate_api_key_hash = hash_string(api_key, DATABASE_HASH_KEY)
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
        return {
            "user_email": row[0],
            "server_url": row[1],
        }
    return None


async def update_user_detail(server_url, user_provider, user_provider_id):
    async with pool.connection() as conn:
        await conn.execute(
            """
            UPDATE users
            SET server_url = %s
            WHERE provider = %s
            AND provider_user_id = %s
            """,
            (server_url, user_provider, user_provider_id),
        )


async def get_jurisdiction_people(jurisdiction_ocdid: str) -> List[Person]:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT data FROM people
                WHERE jurisdiction_ocdid = %s
            """,
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
    if row:
        people_data = row[0]
    else:
        people_data = []
    people = [Person(**d_item) for d_item in people_data]
    return people


async def get_jurisdiction_states() -> List[str]:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT state from jurisdictions
            ORDER by state;
            """,
        )
        results = await cur.fetchall()
        unique_states = [row[0] for row in results]

    return unique_states


async def search_jurisdictions(state: str, limit: int = 100, skip: int = 0):
    """
    Retrieves a paginated list of jurisdictions and the total count for a given state.

    Returns: A tuple (total_count, list_of_jurisdictions)
    """
    if limit <= 0:
        limit = 100  # Set a default reasonable limit if 0 is passed

    print("searching...")
    try:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT COUNT(*) FROM jurisdictions WHERE state = %s;
                """,
                (state.lower(),),
            )
            total_count = (await cur.fetchone())[0]

            await cur.execute(
                """
                SELECT jurisdiction_ocdid_slug, data
                FROM jurisdictions
                WHERE state = %s
                ORDER BY jurisdiction_ocdid  -- Always use ORDER BY with LIMIT/OFFSET
                LIMIT %s OFFSET %s;
                """,
                (state.lower(), limit, skip),
            )

            # Fetch all matching records
            results = await cur.fetchall()
            print("waht are ", results)

            # Process the results
            jurisdictions = []
            for row in results:
                jurisdictions.append({"jurisdiction_ocdid_slug": row[0], **row[1]})

            return total_count, jurisdictions

    except Exception as e:
        print(f"Database error in get_jurisdictions: {e}")
        return 0, []
