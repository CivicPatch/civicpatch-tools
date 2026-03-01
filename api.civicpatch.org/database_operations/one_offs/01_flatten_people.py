import json
import asyncio
from psycopg_pool import AsyncConnectionPool
import os

CIVICPATCH_API_DB_URL = os.getenv("CIVICPATCH_API_DB_URL")
pool = AsyncConnectionPool(CIVICPATCH_API_DB_URL, open=False)

async def flatten_people():
    await pool.open()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT jurisdiction_ocdid, data FROM people")
        rows = await cur.fetchall()
        for jurisdiction_ocdid, people_list in rows:  # data_json is already a list
            for person in people_list:
                await cur.execute(
                    """
                    INSERT INTO people (jurisdiction_ocdid, data)
                    VALUES (%s, %s)
                    """,
                    (jurisdiction_ocdid, json.dumps(person))
                )
        await cur.execute("DELETE FROM people WHERE jsonb_typeof(data) = 'array';")
        await conn.commit()

if __name__ == "__main__":
    asyncio.run(flatten_people())