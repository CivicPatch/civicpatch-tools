import logging
from typing import Any, List, LiteralString

from core.membership_label import rendered_post_label
from database.database import get_pool
from psycopg import sql
from shared.schemas import Person

logger = logging.getLogger(__name__)

# A view over memberships, never a column. `source_labels`, NOT `roles.label` or `posts.label`:
# those are the canonical role, and either would have silently reworded ~4,500 dev people.
#
# Open first, then most recent — a retired person keeps their last seat rather than blanking out
# the day their membership closes. Unaliased, so a caller need not spell `people` any one way.
PERSON_OFFICE = """(
    SELECT jsonb_build_object(
        'name', array_to_string(memberships.source_labels, ' - '),
        'division_ocdid', posts.division_ocdid)
    FROM memberships JOIN posts ON posts.id = memberships.post_id
    WHERE memberships.person_id = people.id
    ORDER BY (memberships.closed_at IS NULL) DESC, memberships.first_seen_at DESC, posts.id
    LIMIT 1
)"""

# Plural because the schema allows it: the unique index is one *open* membership per
# organization. Open only — the history is the memberships read with `?as_of`.
PERSON_MEMBERSHIPS = """COALESCE((
    SELECT jsonb_agg(jsonb_build_object(
        'post_id', posts.id::text,
        'role_id', posts.role_id,
        'role_label', roles.label,
        'division_ocdid', posts.division_ocdid,
        'label', memberships.label,
        'post_label', posts.label,
        'source_labels', to_jsonb(memberships.source_labels)
    ) ORDER BY posts.role_id, posts.division_ocdid, posts.id)
    FROM memberships
    JOIN posts ON posts.id = memberships.post_id
    JOIN roles ON roles.id = posts.role_id
    WHERE memberships.person_id = people.id AND memberships.closed_at IS NULL
), '[]'::jsonb)"""


PERSON_LABELS = """COALESCE((
    SELECT jsonb_agg(DISTINCT source_label)
    FROM memberships, unnest(memberships.source_labels) AS source_label
    WHERE memberships.person_id = people.id AND memberships.closed_at IS NULL
), '[]'::jsonb)"""


# The shape `data` had, assembled from columns. Verified byte-identical across all 20,712 dev
# rows, so readers moved without their callers noticing.
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


# The published side of the review card. The proposed side is derived from sightings in
# `services/roster.py` and filtered by `projected` below, so both sides carry the same keys.
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


def labelled(person: dict) -> dict:
    return {
        **person,
        "memberships": [
            {
                **membership,
                "post_label": rendered_post_label(
                    membership["post_label"],
                    membership["role_label"],
                    membership["division_ocdid"],
                ),
            }
            for membership in person.get("memberships") or []
        ],
    }


ACTIVE_STATUS = "active"


class UnscopedRead(Exception):
    """A read with no jurisdiction and no state would return every person we hold."""


async def get_people(
    jurisdiction_ocdid: str | None = None,
    state: str | None = None,
    status: str | None = None,
) -> list[dict]:
    if jurisdiction_ocdid is None and state is None:
        raise UnscopedRead("pass a jurisdiction_ocdid or a state")

    # Typed LiteralString, so pyright refuses an f-string here — the clauses can only ever be
    # the literals below, and every value goes through a placeholder.
    clauses: list[LiteralString] = []
    values: list[Any] = []

    if jurisdiction_ocdid is not None:
        clauses.append("jurisdiction_ocdid = %s")
        values.append(jurisdiction_ocdid)
    if state is not None:
        clauses.append("jurisdiction_ocdid LIKE %s")
        values.append(f"ocd-jurisdiction/country:us/state:{state.lower()}%")
    if status is not None:
        clauses.append("status = %s")
        values.append(status)

    people: list[dict] = []
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT {PERSON_JSON} FROM people
            WHERE {" AND ".join(clauses)}
            ORDER BY jurisdiction_ocdid, name, id
            """,
            tuple(values),
        )
        while True:
            batch = await cur.fetchmany(200)
            if not batch:
                break
            people.extend(labelled(row[0]) for row in batch)
    return people


async def get_person_models(
    jurisdiction_ocdid: str, status: str | None = None
) -> List[Person]:
    people = await get_people(jurisdiction_ocdid=jurisdiction_ocdid, status=status)
    return [Person(**person) for person in people]


async def get_people_by_jurisdictions(
    jurisdiction_ocdids: list[str], view: str = DEFAULT_VIEW
) -> dict[str, list[dict]]:
    """The published roster of each jurisdiction, projected to a review card's fields."""
    if not jurisdiction_ocdids:
        return {}
    projection = _build_jsonb_obj(
        _PEOPLE_TABLE_EXPRS, VIEWS.get(view, VIEWS[DEFAULT_VIEW])
    )
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            sql.SQL("""
            SELECT jurisdiction_ocdid, {} AS person
            FROM people
            WHERE jurisdiction_ocdid = ANY(%s) AND status = 'active'
            """).format(projection),
            (jurisdiction_ocdids,),
        )
        rows = await cur.fetchall()

    by_jurisdiction: dict[str, list[dict]] = {}
    for jurisdiction_ocdid, person in rows:
        by_jurisdiction.setdefault(jurisdiction_ocdid, []).append(person)
    return by_jurisdiction


def projected(person: dict, view: str = DEFAULT_VIEW) -> dict:
    """A derived person cut down to the same fields the published side is projected to."""
    fields = VIEWS.get(view, VIEWS[DEFAULT_VIEW])
    return {key: value for key, value in person.items() if key in fields}


async def get_people_by_ids(person_ids: list[str]) -> dict[str, Person]:
    if not person_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT {PERSON_JSON} FROM people WHERE id = ANY(%s)", (person_ids,)
        )
        return {
            row[0]["id"]: Person(**labelled(row[0])) for row in await cur.fetchall()
        }


async def filter_existing_person_ids(ids: list[str]) -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM people WHERE id = ANY(%s)",
            (ids,),
        )
        rows = await cur.fetchall()
    return [row[0] for row in rows]


async def get_people_page(
    jurisdiction_ocdid: str, limit: int, offset: int
) -> tuple[int, list[dict]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT COUNT(*) OVER(), {PERSON_JSON}, people.status
            FROM people
            WHERE jurisdiction_ocdid = %s
            ORDER BY
                CASE WHEN people.status = 'active' THEN 0 ELSE 1 END,
                people.updated_at DESC NULLS LAST,
                people.id
            LIMIT %s OFFSET %s
            """,
            (jurisdiction_ocdid, limit, offset),
        )
        rows = await cur.fetchall()
    if not rows:
        return 0, []
    total = rows[0][0]
    return total, [{**labelled(row[1]), "status": row[2]} for row in rows]


async def delete_person(person_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM people WHERE id = %s",
            (person_id,),
        )


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

# One statement for both writers — it was copied in `publications` before 134, and doubling a
# ten-column write is how the two quietly stop agreeing.
PERSON_UPSERT = f"""
    INSERT INTO people (id, jurisdiction_ocdid, updated_at, status, {", ".join(_PERSON_COLUMNS)})
    VALUES (%(id)s, %(jurisdiction_ocdid)s, %(updated_at)s, 'active',
            {", ".join(f"%({column})s" for column in _PERSON_COLUMNS)})
    ON CONFLICT (id) DO UPDATE
       SET updated_at = EXCLUDED.updated_at,
           status = 'active',
           {", ".join(f"{column} = EXCLUDED.{column}" for column in _PERSON_COLUMNS)}
"""


def person_upsert_params(people: list[dict]) -> list[dict]:
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

    records = person_upsert_params(people)
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
