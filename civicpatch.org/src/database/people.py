import logging
from typing import Any, List, LiteralString

from core.membership_label import derive_post_label
from database.database import get_pool
from psycopg import sql
from shared.schemas import Person

logger = logging.getLogger(__name__)

# Open first, then most recent — a retired person keeps their last seat rather than blanking out
# the day their membership closes. Unaliased, so a caller need not spell `people` any one way.
# A term belongs to the tenure, so both come off the seat they hold — the open membership,
# else the most recent, ordered as `PERSON_OFFICE` does. Written out rather than built by a
# function: pyright's `LiteralString` guard is what stops a runtime string reaching `execute`,
# and a helper returning `str` gives that up for six lines.
PERSON_START_DATE = """(
    SELECT memberships.start_date
    FROM memberships
    WHERE memberships.person_id = people.id
    ORDER BY (memberships.closed_at IS NULL) DESC, memberships.first_seen_at DESC
    LIMIT 1
)"""

PERSON_END_DATE = """(
    SELECT memberships.end_date
    FROM memberships
    WHERE memberships.person_id = people.id
    ORDER BY (memberships.closed_at IS NULL) DESC, memberships.first_seen_at DESC
    LIMIT 1
)"""


# Plural because the schema allows it: the unique index is one *open* membership per
# organization. Open only — the history is the memberships read with `?as_of`.
PERSON_MEMBERSHIPS = """COALESCE((
    SELECT jsonb_agg(jsonb_build_object(
        'post_id', posts.id::text,
        'role_id', posts.role_id,
        'role_label', roles.label,
        -- Ranking only; never published. Lower wins, as `core.people_roles` has it.
        'priority', roles.priority,
        'jurisdiction_ocdid', posts.jurisdiction_ocdid,
        'division_ocdid', posts.division_ocdid,
        'label', memberships.label,
        'source_labels', to_jsonb(memberships.source_labels),
        'designations', to_jsonb(memberships.designations),
        'unmatched_text', to_jsonb(memberships.unmatched_text),
        'start_date', memberships.start_date,
        'end_date', memberships.end_date,
        -- When this seat was first and last observed. Both NOT NULL.
        'first_seen_at', memberships.first_seen_at,
        'last_seen_at', memberships.last_seen_at
    ) ORDER BY posts.role_id, posts.division_ocdid, posts.id)
    FROM memberships
    JOIN posts ON posts.id = memberships.post_id
    JOIN roles ON roles.id = posts.role_id
    WHERE memberships.person_id = people.id AND memberships.closed_at IS NULL
), '[]'::jsonb)"""


# The division half of `PERSON_OFFICE`, on its own. Same subquery and same ordering, so the
# two cannot disagree while both exist; `PERSON_OFFICE` goes when its `name` half does.
PERSON_DIVISION = """(
    SELECT posts.division_ocdid
    FROM memberships JOIN posts ON posts.id = memberships.post_id
    WHERE memberships.person_id = people.id
    ORDER BY (memberships.closed_at IS NULL) DESC, memberships.first_seen_at DESC, posts.id
    LIMIT 1
)"""


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
    'start_date', {PERSON_START_DATE},
    'end_date', {PERSON_END_DATE},
    'jurisdiction_ocdid', people.jurisdiction_ocdid,
    'updated_at', to_char(people.updated_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00',
    'labels', {PERSON_LABELS},
    'division_ocdid', {PERSON_DIVISION},
    'memberships', {PERSON_MEMBERSHIPS}
)"""


# The published side of the review card. The proposed side is derived from sightings in
# `services/roster.py` and filtered by `projected` below, so both sides carry the same keys.
_PEOPLE_TABLE_EXPRS: dict[str, tuple[LiteralString, LiteralString]] = {
    "id": ("'id'", "people.id::text"),
    "name": ("'name'", "people.name"),
    "labels": ("'labels'", PERSON_LABELS),
    "division_ocdid": ("'division_ocdid'", PERSON_DIVISION),
    "source_urls": ("'source_urls'", "to_jsonb(people.source_urls)"),
    "phones": ("'phones'", "to_jsonb(people.phones)"),
    "emails": ("'emails'", "to_jsonb(people.emails)"),
    "urls": ("'urls'", "to_jsonb(people.urls)"),
    "start_date": ("'start_date'", PERSON_START_DATE),
    "end_date": ("'end_date'", PERSON_END_DATE),
    "image": ("'image'", "people.image"),
}

_QUICK_FIELDS = frozenset({"id", "name", "labels", "source_urls"})
_DETAIL_FIELDS = frozenset(
    {
        "id",
        "name",
        "labels",
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
                "post_label": derive_post_label(
                    membership["role_label"],
                    membership["division_ocdid"],
                ),
            }
            for membership in person.get("memberships") or []
        ],
    }


# Somebody is on the roster if a publish put them in a seat. `people.status` used to say so
# as a column, set by `PERSON_UPSERT` and cleared by whoever noticed an absence — a cache of
# exactly this, and one that could drift from it. Measured before removing: `inactive` matched
# "no open membership" for 48 of 48, and `active` for 20,644 of 20,664.
IS_ON_THE_ROSTER = """EXISTS (
    SELECT 1 FROM memberships
    WHERE memberships.person_id = people.id AND memberships.closed_at IS NULL
)"""


class UnscopedRead(Exception):
    """A read with no jurisdiction and no state would return every person we hold."""


async def get_roster(
    jurisdiction_ocdid: str | None = None, state: str | None = None
) -> list[dict]:
    """Everyone currently seated — the published roster.

    What `status='active'` used to mean, asked of memberships instead of a column that
    mirrored them.
    """
    return await _people(jurisdiction_ocdid, state, seated_only=True)


async def get_people(
    jurisdiction_ocdid: str | None = None, state: str | None = None
) -> list[dict]:
    """Everyone we hold here, seated or not. The admin and search view."""
    return await _people(jurisdiction_ocdid, state, seated_only=False)


def _scope(
    jurisdiction_ocdid: str | None,
    state: str | None,
    seated_only: bool,
) -> tuple[list[LiteralString], list[Any]]:
    """The WHERE clauses and their values, shared by the whole read and the paged one.

    Typed LiteralString, so pyright refuses an f-string here — the clauses can only ever be the
    literals below, and every value goes through a placeholder.
    """
    if jurisdiction_ocdid is None and state is None:
        raise UnscopedRead("pass a jurisdiction_ocdid or a state")

    clauses: list[LiteralString] = []
    values: list[Any] = []

    if jurisdiction_ocdid is not None:
        clauses.append("jurisdiction_ocdid = %s")
        values.append(jurisdiction_ocdid)
    if state is not None:
        clauses.append("jurisdiction_ocdid LIKE %s")
        values.append(f"ocd-jurisdiction/country:us/state:{state.lower()}%")
    if seated_only:
        clauses.append(IS_ON_THE_ROSTER)
    return clauses, values


async def get_roster_page(
    jurisdiction_ocdid: str | None, state: str | None, limit: int, offset: int
) -> tuple[int, list[dict]]:
    """One page of the seated roster, and the total behind it.

    Same filters and ordering as `get_roster`, so paging through it walks the same list.
    """
    clauses, values = _scope(jurisdiction_ocdid, state, seated_only=True)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT COUNT(*) OVER(), {PERSON_JSON} FROM people
            WHERE {" AND ".join(clauses)}
            ORDER BY jurisdiction_ocdid, name, id
            LIMIT %s OFFSET %s
            """,
            tuple(values) + (limit, offset),
        )
        rows = await cur.fetchall()
    if not rows:
        return 0, []
    return rows[0][0], [labelled(row[1]) for row in rows]


async def _people(
    jurisdiction_ocdid: str | None,
    state: str | None,
    seated_only: bool,
) -> list[dict]:
    clauses, values = _scope(jurisdiction_ocdid, state, seated_only)

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


async def get_person_models(jurisdiction_ocdid: str) -> List[Person]:
    people = await get_people(jurisdiction_ocdid=jurisdiction_ocdid)
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
            WHERE jurisdiction_ocdid = ANY(%s) AND """ + IS_ON_THE_ROSTER).format(
                projection
            ),
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
            SELECT COUNT(*) OVER(), {PERSON_JSON}, {IS_ON_THE_ROSTER}
            FROM people
            WHERE jurisdiction_ocdid = %s
            ORDER BY
                CASE WHEN {IS_ON_THE_ROSTER} THEN 0 ELSE 1 END,
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
    # `status` on the way out is derived, not read: the seated come first and say so, which is
    # what the column was for.
    return total, [
        {**labelled(row[1]), "status": "active" if row[2] else "inactive"}
        for row in rows
    ]


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
)
_LIST_COLUMNS = frozenset({"other_names", "phones", "emails", "urls", "source_urls"})

# One statement, so the writers cannot quietly stop agreeing. No `status`: whether somebody is
# on the roster is `IS_ON_THE_ROSTER`, asked of memberships.
# `updated_at` is stamped here, not carried by the caller, so no writer can put a stale value
# back. The WHERE is why it stays meaningful: `DO UPDATE` fires on every conflict whether or not
# anything differs, so without it a republish of an unchanged roster would move every person's
# `updated_at` and diff the published file for nothing.
PERSON_UPSERT = f"""
    INSERT INTO people (id, jurisdiction_ocdid, updated_at, {", ".join(_PERSON_COLUMNS)})
    VALUES (%(id)s, %(jurisdiction_ocdid)s, now(),
            {", ".join(f"%({column})s" for column in _PERSON_COLUMNS)})
    ON CONFLICT (id) DO UPDATE
       SET updated_at = now(),
           {", ".join(f"{column} = EXCLUDED.{column}" for column in _PERSON_COLUMNS)}
     WHERE ({", ".join(f"people.{column}" for column in _PERSON_COLUMNS)})
        IS DISTINCT FROM
           ({", ".join(f"EXCLUDED.{column}" for column in _PERSON_COLUMNS)})
"""


def person_upsert_params(people: list[dict]) -> list[dict]:
    """A roster's dicts as rows for `PERSON_UPSERT`.

    One caller now — `publish_request`. It also shaped the people files `od_sync` read back,
    until that read-back was removed.
    """
    return [
        {
            "id": person.get("id"),
            "jurisdiction_ocdid": person.get("jurisdiction_ocdid"),
            **{
                column: (person.get(column) or [])
                if column in _LIST_COLUMNS
                else person.get(column)
                for column in _PERSON_COLUMNS
            },
        }
        for person in people
    ]
