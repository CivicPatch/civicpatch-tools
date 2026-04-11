import os
import logging
from typing import Any
from database.database import get_pool
import services.storage_service
import shared.utils.data_path_utils
import shared.utils.url_utils

logger = logging.getLogger(__name__)

_PEOPLE_TABLE_EXPRS = {
    "id":          ("'id'",          "data#>>'{id}'"),
    "name":        ("'name'",        "data#>>'{name}'"),
    "office":      ("'office'",      "jsonb_build_object('name', data#>>'{office,name}', 'division_ocdid', data#>>'{office,division_ocdid}')"),
    "source_urls": ("'source_urls'", "data#>'{source_urls}'"),
    "phones":      ("'phones'",      "data#>'{phones}'"),
    "emails":      ("'emails'",      "data#>'{emails}'"),
    "urls":        ("'urls'",        "data#>'{urls}'"),
    "start_date":  ("'start_date'",  "data#>>'{start_date}'"),
    "end_date":    ("'end_date'",    "data#>>'{end_date}'"),
    "image":       ("'image'",       "data#>>'{image}'"),
}

_RESULT_JSON_EXPRS = {
    "id":          ("'id'",          "elem->>'id'"),
    "name":        ("'name'",        "elem->>'name'"),
    "office":      ("'office'",      "jsonb_build_object('name', elem#>>'{office,name}', 'division_ocdid', elem#>>'{office,division_ocdid}')"),
    "source_urls": ("'source_urls'", "elem->'source_urls'"),
    "phones":      ("'phones'",      "elem->'phones'"),
    "emails":      ("'emails'",      "elem->'emails'"),
    "urls":        ("'urls'",        "elem->'urls'"),
    "start_date":  ("'start_date'",  "elem->>'start_date'"),
    "end_date":    ("'end_date'",    "elem->>'end_date'"),
    "image":       ("'image'",       "elem->>'image'"),
}

_QUICK_FIELDS = frozenset({"id", "name", "office", "source_urls"})
_DETAIL_FIELDS = frozenset({"id", "name", "office", "source_urls", "phones", "emails", "urls", "start_date", "end_date", "image"})

VIEWS: dict[str, frozenset[str]] = {
    "quick": _QUICK_FIELDS,
    "detail": _DETAIL_FIELDS,
}
DEFAULT_VIEW = "quick"


def _build_jsonb_obj(exprs: dict, fields: frozenset[str]) -> str:
    parts = []
    for field in sorted(fields):
        if field in exprs:
            key, val = exprs[field]
            parts += [key, val]
    return f"jsonb_build_object({', '.join(parts)})"


async def get_people_by_jurisdiction_ocdid(
    jurisdiction_ocdid: str,
) -> list[dict[str, Any]]:
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
    jurisdiction_ocdids: list[str],
    request_ids: list[str],
    view: str = DEFAULT_VIEW,
) -> dict[str, dict[str, Any]]:
    fields = VIEWS.get(view, VIEWS[DEFAULT_VIEW])

    people_projection = _build_jsonb_obj(_PEOPLE_TABLE_EXPRS, fields)
    result_projection = _build_jsonb_obj(_RESULT_JSON_EXPRS, fields)

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"""
                SELECT jurisdiction_ocdid, {people_projection} AS person
                FROM people
                WHERE jurisdiction_ocdid = ANY(%s)
                  AND status = 'current'
                """,
                (jurisdiction_ocdids,)
            )
            people_rows = await cur.fetchall()

            await cur.execute(
                f"""
                SELECT
                    r.id::text AS request_id,
                    (
                        SELECT jsonb_agg({result_projection})
                        FROM jsonb_array_elements(r.data_json) AS elem
                    ) AS people_data,
                    r.jurisdiction_ocdid
                FROM requests r
                WHERE r.id = ANY(%s)
                """,
                (request_ids,)
            )
            jobs_rows = await cur.fetchall()

    people_map: dict[str, list] = {}
    for jurisdiction, person in people_rows:
        people_map.setdefault(jurisdiction, []).append(person)

    results: dict[str, dict[str, Any]] = {}
    for request_id, people_data, jurisdiction_ocdid in jobs_rows:
        results[request_id] = {
            "existing": people_map.get(jurisdiction_ocdid, []),
            "proposed": people_data or [],  # jsonb_agg returns None for empty/null result_data
        }

    return results
