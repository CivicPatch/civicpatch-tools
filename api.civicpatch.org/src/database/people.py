import json
from typing import List, Dict, Any
from database.database import get_pool

async def get_pull_request_data_by_request_ids(
    jurisdiction_ocdids: List[str], request_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dict keyed by request_id, with:
      - 'existing': people for the jurisdiction_ocdid (from people table)
      - 'pull_request': result_json for the request_id (from jobs table)
    """
    pool = await get_pool()
    results = {}

    # Fetch people data for each jurisdiction_ocdid
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    jurisdiction_ocdid,
                    data#>>'{id}' AS id,
                    data#>>'{name}' AS name,
                    data#>>'{office,name}' AS office_name,
                    data#>>'{office,division_ocdid}' AS office_division_ocdid,
                    data#>>'{source_urls}' AS source_urls
                FROM people
                WHERE jurisdiction_ocdid = ANY(%s)
                  AND status = 'current'
                """,
                (jurisdiction_ocdids,)
            )
            people_rows = await cur.fetchall()

    # Build a map of jurisdiction_ocdid -> people[]
    people_map = {}
    for row in people_rows:
        jurisdiction = row[0]
        person = {
            "jurisdiction_ocdid": jurisdiction,
            "id": row[1],
            "name": row[2],
            "office": {
                "name": row[3],
                "division_ocdid": row[4],
            },
            "source_urls": json.loads(row[5]) if row[5] else []
        }
        people_map.setdefault(jurisdiction, []).append(person)

    # Fetch jobs data for each request_id
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    request_id,
                    result_json,
                    arguments_json#>>'{jurisdiction_ocdid}' as jurisdiction_ocdid
                FROM jobs
                WHERE request_id = ANY(%s)
                """,
                (request_ids,)
            )
            jobs_rows = await cur.fetchall()

    for row in jobs_rows:
        request_id = row[0]
        result_json = row[1]
        jurisdiction_ocdid = row[2]
        results[request_id] = {
            "existing": people_map.get(jurisdiction_ocdid, []),
            "pull_request": []
        }
        if result_json:
            try:
                pr_list = json.loads(result_json) if isinstance(result_json, str) else result_json
                if isinstance(pr_list, list):
                    results[request_id]["pull_request"].extend(pr_list)
            except Exception:
                pass

    return results