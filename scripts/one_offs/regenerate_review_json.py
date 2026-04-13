#!/usr/bin/env python3
"""
One-off script: regenerate review_json for all requests that have result_data,
using current DB people as the research baseline (origin_source="existing")
instead of the Gemini research step output.

Run: mise run regenerate-review-json
"""
import asyncio
import json
import logging
import os

from psycopg_pool import AsyncConnectionPool

from shared.schemas import Person
from shared.utils import config_utils, name_utils
from shared.utils.review_utils import generate_review, ReviewInputs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_requests(pool: AsyncConnectionPool) -> list[dict]:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, jurisdiction_ocdid, result_data
            FROM requests
            WHERE result_data IS NOT NULL
              AND jsonb_array_length(result_data) > 0
            """
        )
        rows = await cur.fetchall()
    return [
        {"request_id": str(row[0]), "jurisdiction_ocdid": row[1], "result_data": row[2]}
        for row in rows
    ]


async def get_people(pool: AsyncConnectionPool, jurisdiction_ocdid: str, status: str = None) -> list[Person]:
    async with pool.connection() as conn, conn.cursor() as cur:
        if status is not None:
            await cur.execute(
                "SELECT data FROM people WHERE jurisdiction_ocdid = %s AND status = %s",
                (jurisdiction_ocdid, status),
            )
        else:
            await cur.execute(
                "SELECT data FROM people WHERE jurisdiction_ocdid = %s",
                (jurisdiction_ocdid,),
            )
        rows = await cur.fetchall()
    return [Person(**row[0]) for row in rows]


async def update_review_json(pool: AsyncConnectionPool, request_id: str, review: dict) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE requests SET review_json = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (json.dumps(review), request_id),
        )


async def main() -> None:
    db_url = os.environ["CIVICPATCH_API_DB_URL"]
    pool = AsyncConnectionPool(db_url, open=False, min_size=1, max_size=4)
    await pool.open()

    try:
        requests = await get_requests(pool)
        logger.info("Processing %d request(s).", len(requests))

        for req in requests:
            request_id = req["request_id"]
            jurisdiction_ocdid = req["jurisdiction_ocdid"]
            result_data = req["result_data"]

            current_people = await get_people(pool, jurisdiction_ocdid, status="current")
            all_people = await get_people(pool, jurisdiction_ocdid)

            identities = name_utils.person_list_to_identities(all_people)
            origin_source = "existing" if current_people else "google_gemini"

            inputs = ReviewInputs(
                identities=identities,
                unique_roles=config_utils.get_unique_roles(),
            )
            review = generate_review(current_people, result_data, inputs, origin_source)

            await update_review_json(pool, request_id, review)
            logger.info(
                "Updated %s (%s): origin=%s, issues=%d",
                request_id,
                jurisdiction_ocdid,
                origin_source,
                len(review["issues"]),
            )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
