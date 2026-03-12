import logging
from typing import Any
from database.database import get_pool

logger = logging.getLogger(__name__)

async def get_people_by_jurisdiction_ocdid(
    jurisdiction_ocdid: str,
) -> list[dict[str, Any]]:
    """
    Returns all current people for a given jurisdiction_ocdid.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT data
                FROM people
                WHERE jurisdiction_ocdid = %s
                  AND status = 'current'
                """,
                (jurisdiction_ocdid,)
            )
            rows = await cur.fetchall()

    return [row[0] for row in rows]


async def get_people_data_by_request_ids(
    jurisdiction_ocdids: list[str], request_ids: list[str]
) -> dict[str, dict[str, Any]]:
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:

            # People
            await cur.execute(
                """
                SELECT
                    jurisdiction_ocdid,
                    data#>>'{id}'                   AS id,
                    data#>>'{name}'                 AS name,
                    data#>>'{office,name}'          AS office_name,
                    data#>>'{office,division_ocdid}' AS office_division_ocdid,
                    data#>>'{source_urls}'          AS source_urls
                FROM people
                WHERE jurisdiction_ocdid = ANY(%s)
                  AND status = 'current'
                """,
                (jurisdiction_ocdids,)
            )
            people_rows = await cur.fetchall()

            # Jobs
            await cur.execute(
                """
                SELECT
                    request_id,
                    result_json,
                    arguments_json#>>'{jurisdiction_ocdid}' AS jurisdiction_ocdid
                FROM jobs
                WHERE request_id = ANY(%s)
                """,
                (request_ids,)
            )
            jobs_rows = await cur.fetchall()

    # Build jurisdiction -> people map
    people_map: dict[str, list] = {}
    for row in people_rows:
        jurisdiction, id_, name, office_name, office_div, source_urls = row
        people_map.setdefault(jurisdiction, []).append({
            "jurisdiction_ocdid": jurisdiction,
            "id": id_,
            "name": name,
            "office": {
                "name": office_name,
                "division_ocdid": office_div,
            },
            "source_urls": source_urls if isinstance(source_urls, list) else (
                __import__('json').loads(source_urls) if source_urls else []
            ),
        })

    # Assemble results
    results: dict[str, dict[str, Any]] = {}
    for request_id, result_json, jurisdiction_ocdid in jobs_rows:
        pr_list = []
        if result_json:
            try:
                parsed = result_json if isinstance(result_json, list) else __import__('json').loads(result_json)
                if isinstance(parsed, list):
                    pr_list = parsed
            except Exception:
                logger.warning("Failed to parse result_json for request_id=%s", request_id)

        results[request_id] = {
            "existing": people_map.get(jurisdiction_ocdid, []),
            "pull_request": pr_list,
        }

    return results