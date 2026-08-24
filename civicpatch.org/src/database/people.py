import logging
from typing import Any, List, LiteralString

from database.database import get_pool
from psycopg import sql
from shared.schemas import Person

logger = logging.getLogger(__name__)

# `office` is a view over memberships, never a column — role and division already live there.
#
# `source_labels` joined with " - ", which is the join `office_name_to_labels` splits back
# apart. NOT `roles.label` or `posts.label`: those are the *canonical* role, a different value,
# and measured against dev either would have silently reworded ~4,500 people. 78% and 67%
# respectively — close enough to look right in a spot check.
#
# A retired person falls back to the last post they held, so the office does not blank out the
# day their membership closes. `PERSON_MEMBERSHIPS` deliberately does not do this — "where do
# they serve" is present tense — but `office` is the one line a card prints, and a councilmember
# who left in March still reads better as their seat than as nothing.
#
# Still open first, then most recent. This replaced a `people.data->'office'` fallback and was
# the last reader of that column.
#
# Unaliased, so a caller cannot be required to spell `people` any particular way.
PERSON_OFFICE = """(
    SELECT jsonb_build_object(
        'name', array_to_string(memberships.source_labels, ' - '),
        'division_ocdid', posts.division_ocdid)
    FROM memberships JOIN posts ON posts.id = memberships.post_id
    WHERE memberships.person_id = people.id
    ORDER BY (memberships.closed_at IS NULL) DESC, memberships.first_seen_at DESC
    LIMIT 1
)"""

# Where a person serves, inline. Plural because the schema already allows it: the unique index
# is one *open* membership per organization, and a jurisdiction can have several bodies. Every
# person holds exactly one post today (20,644 of 20,644 on dev), so `office` was accurate — but
# it was singular by accident, not by rule.
#
# Open memberships only. "Where do they serve" is present tense; the history is the memberships
# read with `?as_of`, which windows on `first_seen_at`/`closed_at`.
#
# `source_labels` rides along because it is what `office.name` always was — the source's own
# words — and the readers replacing `office` need it to say the same thing they say today.
PERSON_MEMBERSHIPS = """COALESCE((
    SELECT jsonb_agg(jsonb_build_object(
        'post_id', posts.id::text,
        'role_id', posts.role_id,
        'role_label', roles.label,
        'division_ocdid', posts.division_ocdid,
        'label', memberships.label,
        'post_label', posts.label,
        'source_labels', to_jsonb(memberships.source_labels)
    ) ORDER BY posts.role_id, posts.division_ocdid)
    FROM memberships
    JOIN posts ON posts.id = memberships.post_id
    JOIN roles ON roles.id = posts.role_id
    WHERE memberships.person_id = people.id AND memberships.closed_at IS NULL
), '[]'::jsonb)"""


# What the source called this person, as a list. The same words `data_json` carries as
# `labels` on a proposed record — which is what lets the review card diff the two sides on one
# key instead of on a string we joined.
# `source_label`, not `label`: `memberships.label` exists, so the bare alias is ambiguous.
PERSON_LABELS = """COALESCE((
    SELECT jsonb_agg(DISTINCT source_label)
    FROM memberships, unnest(memberships.source_labels) AS source_label
    WHERE memberships.person_id = people.id AND memberships.closed_at IS NULL
), '[]'::jsonb)"""


# One person, in the shape `data` has always had, assembled from columns instead.
#
# Verified against all 20,712 dev rows: byte-identical to `data`, `office` and the ISO
# `updated_at` included. That equality is the point — readers move without their callers
# noticing, and the flat shape becomes a separate, later decision.
PERSON_JSON = f"""jsonb_build_object(
    'id', people.id::text,
    'name', people.name,
    'other_names', to_jsonb(people.other_names),
    'phones', to_jsonb(people.phones),
    'emails', to_jsonb(people.emails),
    'urls', to_jsonb(people.urls),
    'source_urls', to_jsonb(people.source_urls),
    'image', people.image,
    'cdn_image', people.cdn_image,
    'start_date', people.start_date,
    'end_date', people.end_date,
    'jurisdiction_ocdid', people.jurisdiction_ocdid,
    'updated_at', to_char(people.updated_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00',
    'labels', {PERSON_LABELS},
    'office', {PERSON_OFFICE},
    'memberships', {PERSON_MEMBERSHIPS}
)"""


# The people side of the review card. Columns since 134; `office` is the memberships view.
# Its twin below still reads `data_json`, because that is a *proposed* roster from the
# pipeline, not a row — the two must keep emitting the same KEYS or the card cannot diff them.
_PEOPLE_TABLE_EXPRS: dict[str, tuple[LiteralString, LiteralString]] = {
    "id": ("'id'", "people.id::text"),
    "name": ("'name'", "people.name"),
    "labels": ("'labels'", PERSON_LABELS),
    "office": ("'office'", PERSON_OFFICE),
    "source_urls": ("'source_urls'", "to_jsonb(people.source_urls)"),
    "phones": ("'phones'", "to_jsonb(people.phones)"),
    "emails": ("'emails'", "to_jsonb(people.emails)"),
    "urls": ("'urls'", "to_jsonb(people.urls)"),
    "start_date": ("'start_date'", "people.start_date"),
    "end_date": ("'end_date'", "people.end_date"),
    "image": ("'image'", "people.image"),
}

_RESULT_JSON_EXPRS: dict[str, tuple[LiteralString, LiteralString]] = {
    "id": ("'id'", "elem->>'id'"),
    "name": ("'name'", "elem->>'name'"),
    # The proposed roster carries `labels` directly since the records flip; `office` is the
    # joined string it is replacing, still projected while readers move.
    "labels": ("'labels'", "COALESCE(elem->'labels', '[]'::jsonb)"),
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

_QUICK_FIELDS = frozenset({"id", "name", "labels", "office", "source_urls"})
_DETAIL_FIELDS = frozenset(
    {
        "id",
        "name",
        "labels",
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
                f"""
                SELECT {PERSON_JSON}
                FROM people
                WHERE jurisdiction_ocdid = %s
                  AND status = 'active'
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
                  AND status = 'active'
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


# `past` = absent from the open-data file, so publishing them fails validation.
async def get_jurisdiction_people(jurisdiction_ocdid: str) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
                SELECT {PERSON_JSON} FROM people
                WHERE jurisdiction_ocdid = %s AND status = 'active'
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
            f"""
            SELECT COUNT(*) OVER(), people.id::text, {PERSON_JSON}, people.status
            FROM people
            WHERE jurisdiction_ocdid = %s
            ORDER BY
                CASE WHEN people.status = 'active' THEN 0 ELSE 1 END,
                people.updated_at DESC NULLS LAST
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


# The columns 134 split out of `data`. Named here so the row builder and the statement below
# cannot drift — they are the two halves of one contract.
_PERSON_COLUMNS = (
    "name",
    "other_names",
    "phones",
    "emails",
    "urls",
    "source_urls",
    "image",
    "cdn_image",
    "start_date",
    "end_date",
)
_LIST_COLUMNS = frozenset({"other_names", "phones", "emails", "urls", "source_urls"})

# One statement for both writers. It was copied in `publications` before 134, and doubling a
# ten-column write is how the two quietly stop agreeing.
#
# The columns are the record now. `data` was authoritative until 134 split it out and every
# reader moved; writing it after that would keep a second copy nothing consults, which is how
# the two halves start disagreeing without anybody noticing.
PERSON_UPSERT = f"""
    INSERT INTO people (id, jurisdiction_ocdid, updated_at, status, {", ".join(_PERSON_COLUMNS)})
    VALUES (%(id)s, %(jurisdiction_ocdid)s, %(updated_at)s, 'active',
            {", ".join(f"%({column})s" for column in _PERSON_COLUMNS)})
    ON CONFLICT (id) DO UPDATE
       SET updated_at = EXCLUDED.updated_at,
           status = 'active',
           {", ".join(f"{column} = EXCLUDED.{column}" for column in _PERSON_COLUMNS)}
"""


def people_rows(people: list[dict]) -> list[dict]:
    """Shape parsed person dicts into the rows `people` stores.

    Named rather than positional: thirteen values in a tuple is a column/value misalignment
    waiting to happen, and the columns arrived all at once in 134.

    `office` is not among them — role and division live on posts/memberships.
    """
    return [
        {
            "id": person.get("id"),
            "jurisdiction_ocdid": person.get("jurisdiction_ocdid"),
            "updated_at": person.get("updated_at"),
            **{
                column: (person.get(column) or [])
                if column in _LIST_COLUMNS
                else person.get(column)
                for column in _PERSON_COLUMNS
            },
        }
        for person in people
    ]


async def bulk_update_people(people: list[dict]):
    if not people:
        return

    records = people_rows(people)
    jurisdictions: dict = {}
    for record in records:
        jurisdictions.setdefault(record["jurisdiction_ocdid"], []).append(record["id"])

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.executemany(PERSON_UPSERT, records)

        for jurisdiction_ocdid, incoming_ids in jurisdictions.items():
            await cur.execute(
                """
                UPDATE people
                SET status = 'inactive'
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
                f"""
                SELECT {PERSON_JSON} FROM people
                WHERE jurisdiction_ocdid = %s AND status = %s
                """,
                (jurisdiction_ocdid, status),
            )
        else:
            await cur.execute(
                f"""
                SELECT {PERSON_JSON} FROM people
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
            f"""
            SELECT jurisdiction_ocdid, {PERSON_JSON}
            FROM people
            WHERE jurisdiction_ocdid LIKE %s
              AND status = 'active'
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
