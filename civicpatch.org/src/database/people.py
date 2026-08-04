import json
import logging
from typing import Any, List, LiteralString

from database.database import get_pool
from psycopg import sql
from shared.schemas import Person

logger = logging.getLogger(__name__)

_PEOPLE_TABLE_EXPRS: dict[str, tuple[LiteralString, LiteralString]] = {
    "id": ("'id'", "data#>>'{id}'"),
    "name": ("'name'", "data#>>'{name}'"),
    "office": (
        "'office'",
        "jsonb_build_object('name', data#>>'{office,name}', 'division_ocdid', data#>>'{office,division_ocdid}')",
    ),
    "source_urls": ("'source_urls'", "data#>'{source_urls}'"),
    "phones": ("'phones'", "data#>'{phones}'"),
    "emails": ("'emails'", "data#>'{emails}'"),
    "urls": ("'urls'", "data#>'{urls}'"),
    "start_date": ("'start_date'", "data#>>'{start_date}'"),
    "end_date": ("'end_date'", "data#>>'{end_date}'"),
    "image": ("'image'", "data#>>'{image}'"),
}

_RESULT_JSON_EXPRS: dict[str, tuple[LiteralString, LiteralString]] = {
    "id": ("'id'", "elem->>'id'"),
    "name": ("'name'", "elem->>'name'"),
    "office": (
        "'office'",
        "jsonb_build_object('name', elem#>>'{office,name}', 'division_ocdid', elem#>>'{office,division_ocdid}')",
    ),
    "source_urls": ("'source_urls'", "elem->'source_urls'"),
    "phones": ("'phones'", "elem->'phones'"),
    "emails": ("'emails'", "elem->'emails'"),
    "urls": ("'urls'", "elem->'urls'"),
    "start_date": ("'start_date'", "elem->>'start_date'"),
    "end_date": ("'end_date'", "elem->>'end_date'"),
    "image": ("'image'", "elem->>'image'"),
}

_QUICK_FIELDS = frozenset({"id", "name", "office", "source_urls"})
_DETAIL_FIELDS = frozenset(
    {
        "id",
        "name",
        "office",
        "source_urls",
        "phones",
        "emails",
        "urls",
        "start_date",
        "end_date",
        "image",
    }
)

VIEWS: dict[str, frozenset[str]] = {
    "quick": _QUICK_FIELDS,
    "detail": _DETAIL_FIELDS,
}
DEFAULT_VIEW = "quick"


def _build_jsonb_obj(
    exprs: dict[str, tuple[LiteralString, LiteralString]], fields: frozenset[str]
) -> sql.Composed:
    pairs: list[sql.Composable] = []
    for field in sorted(fields):
        if field in exprs:
            key, val = exprs[field]
            pairs.append(sql.SQL(key))
            pairs.append(sql.SQL(val))
    return sql.SQL("jsonb_build_object({})").format(sql.SQL(", ").join(pairs))


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
                (jurisdiction_ocdid,),
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
                sql.SQL("""
                SELECT jurisdiction_ocdid, {} AS person
                FROM people
                WHERE jurisdiction_ocdid = ANY(%s)
                  AND status = 'current'
                """).format(people_projection),
                (jurisdiction_ocdids,),
            )
            people_rows = await cur.fetchall()

            await cur.execute(
                sql.SQL("""
                SELECT
                    r.id::text AS request_id,
                    (
                        SELECT jsonb_agg({})
                        FROM jsonb_array_elements(r.data_json) AS elem
                    ) AS people_data,
                    r.jurisdiction_ocdid
                FROM requests r
                WHERE r.id = ANY(%s)
                """).format(result_projection),
                (request_ids,),
            )
            jobs_rows = await cur.fetchall()

    people_map: dict[str, list] = {}
    for jurisdiction, person in people_rows:
        people_map.setdefault(jurisdiction, []).append(person)

    results: dict[str, dict[str, Any]] = {}
    for request_id, people_data, jurisdiction_ocdid in jobs_rows:
        results[request_id] = {
            "existing": people_map.get(jurisdiction_ocdid, []),
            "proposed": people_data
            or [],  # jsonb_agg returns None for empty/null result_data
        }

    return results


async def filter_existing_person_ids(ids: list[str]) -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM people WHERE id = ANY(%s)",
            (ids,),
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


# `past` means the person is no longer in the open-data file (see mark-past in
# upsert). Returning them puts people in the editor who are absent from the base
# it publishes against, which fails validation for everyone on the page.
async def get_jurisdiction_people(jurisdiction_ocdid: str) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT data FROM people
                WHERE jurisdiction_ocdid = %s AND status = 'current'
            """,
            (jurisdiction_ocdid,),
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


async def get_all_people_for_jurisdiction(
    jurisdiction_ocdid: str, limit: int, offset: int
) -> tuple[int, list[dict]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT COUNT(*) OVER(), id::text, data, status
            FROM people
            WHERE jurisdiction_ocdid = %s
            ORDER BY
                CASE WHEN status = 'current' THEN 0 ELSE 1 END,
                (data->>'updated_at') DESC NULLS LAST
            LIMIT %s OFFSET %s
            """,
            (jurisdiction_ocdid, limit, offset),
        )
        rows = await cur.fetchall()
    if not rows:
        return 0, []
    total = rows[0][0]
    return total, [{**row[2], "_id": row[1], "status": row[3]} for row in rows]


async def delete_person(person_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM people WHERE id = %s",
            (person_id,),
        )


def people_rows(people: list[dict]) -> list[tuple]:
    # Shape parsed person dicts into the (id, jurisdiction_ocdid, data, updated_at) rows the
    # people table stores. Each person carries its own jurisdiction_ocdid; the whole dict is
    # the jsonb `data` column. Pure — the DB layer owns its row format in one place.
    return [
        (p.get("id"), p.get("jurisdiction_ocdid"), json.dumps(p), p.get("updated_at"))
        for p in people
    ]


async def bulk_update_people(people: list[dict]):
    if not people:
        return

    records = people_rows(people)
    jurisdictions: dict = {}
    for record in records:
        person_id, jurisdiction_ocdid = record[0], record[1]
        if jurisdiction_ocdid not in jurisdictions:
            jurisdictions[jurisdiction_ocdid] = []
        jurisdictions[jurisdiction_ocdid].append(person_id)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        insert_query = """
            INSERT INTO people (id, jurisdiction_ocdid, data, updated_at, status)
            VALUES (%s, %s, %s, %s, 'current')
            ON CONFLICT (id)
            DO UPDATE SET
                data = EXCLUDED.data,
                updated_at = EXCLUDED.updated_at,
                status = 'current'
        """
        await cur.executemany(insert_query, records)

        for jurisdiction_ocdid, incoming_ids in jurisdictions.items():
            await cur.execute(
                """
                UPDATE people
                SET status = 'past'
                WHERE jurisdiction_ocdid = %s
                  AND id != ALL(%s)
                """,
                (jurisdiction_ocdid, incoming_ids),
            )


async def get_people_for_jurisdiction(
    jurisdiction_ocdid: str, status: str | None = None
) -> List[Person]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        if status is not None:
            await cur.execute(
                """
                SELECT data FROM people
                WHERE jurisdiction_ocdid = %s AND status = %s
                """,
                (jurisdiction_ocdid, status),
            )
        else:
            await cur.execute(
                """
                SELECT data FROM people
                WHERE jurisdiction_ocdid = %s
                """,
                (jurisdiction_ocdid,),
            )
        rows = await cur.fetchall()
        people = [Person(**row[0]) for row in rows]
    return people


async def get_people_by_state(state: str) -> list[dict]:
    state_prefix = f"ocd-jurisdiction/country:us/state:{state.lower()}%"
    pool = await get_pool()
    rows = []
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT jurisdiction_ocdid, data
            FROM people
            WHERE jurisdiction_ocdid LIKE %s
              AND status = 'current'
            ORDER BY jurisdiction_ocdid
            """,
            (state_prefix,),
        )
        while True:
            batch = await cur.fetchmany(200)
            if not batch:
                break
            rows.extend(batch)
    return [{"jurisdiction_ocdid": r[0], **r[1]} for r in rows]
