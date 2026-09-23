import logging
import uuid
from typing import Any, AsyncGenerator, List, LiteralString

from core.membership_label import derive_post_label
from database import assertions
from database.activity import record_change
from database.changesets import register_people_edit_changeset
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.assertions import (
    DefaultNote,
    Assertion,
    AssertionKind,
    EntityType,
    Source,
)
from schemas.activity import Change
from shared.utils.id_utils import make_id
from shared.utils.statuses import ActivityType
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
        'organization_id', posts.organization_id::text,
        'role_id', posts.role_id,
        'role_label', roles.label,
        -- Ranking only; never published. Lower wins, as `core.people_roles` has it.
        'priority', roles.priority,
        'jurisdiction_ocdid', posts.jurisdiction_ocdid,
        'division_ocdid', posts.division_ocdid,
        'label', memberships.label,
        'source_labels', to_jsonb(membership_source_labels(memberships.sources)),
        -- The pages behind this membership. The pipeline seeds each body's next crawl from
        -- them, so a body whose roster is one person keeps its page in the frontier.
        'source_urls', COALESCE((
            SELECT jsonb_agg(DISTINCT source->>'url')
            FROM jsonb_array_elements(memberships.sources) AS source
            WHERE source->>'url' IS NOT NULL
        ), '[]'::jsonb),
        'designations', to_jsonb(memberships.designations),
        'meta_unmatched_text', to_jsonb(memberships.meta_unmatched_text),
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
    SELECT jsonb_agg(DISTINCT source->>'note')
    FROM memberships, jsonb_array_elements(memberships.sources) AS source
    WHERE memberships.person_id = people.id AND memberships.closed_at IS NULL
), '[]'::jsonb)"""


# `PERSON_LABELS` without the pooling: each open membership's sources keep the organization they
# are held in, so re-deriving a published roster puts a person back into each body separately.
PERSON_SIGHTINGS = """COALESCE((
    SELECT jsonb_agg(DISTINCT jsonb_build_object(
        'label', source->>'note',
        'source_url', source->>'url',
        'organization_id', memberships.organization_id::text
    ))
    FROM memberships, jsonb_array_elements(memberships.sources) AS source
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
    'sightings', {PERSON_SIGHTINGS},
    'division_ocdid', {PERSON_DIVISION},
    'memberships', {PERSON_MEMBERSHIPS}
)"""


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
#
# The NOT EXISTS (189): a retracted membership (memberships.retract — a reject assertion,
# entity_type='membership') is not closed and its row is not deleted, so `closed_at IS NULL`
# alone would still count it. Alias-free throughout, per CLAUDE.md, so any caller that already
# does `FROM people`/`FROM memberships` unaliased can splice this in unchanged.
# A rejected membership is not a row with a claim against it any more: the fold does not derive
# it, so the writer does not insert it. Being on the roster is holding an open membership.
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


async def get_rosters_by_jurisdiction(
    jurisdiction_ocdids: list[str],
) -> dict[str, list[dict]]:
    """`get_roster` for many jurisdictions in one query, every field."""
    if not jurisdiction_ocdids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT jurisdiction_ocdid, {PERSON_JSON} FROM people
            WHERE jurisdiction_ocdid = ANY(%s) AND {IS_ON_THE_ROSTER}
            ORDER BY jurisdiction_ocdid, name, id
            """,
            (jurisdiction_ocdids,),
        )
        rows = await cur.fetchall()

    by_jurisdiction: dict[str, list[dict]] = {}
    for jurisdiction_ocdid, person in rows:
        by_jurisdiction.setdefault(jurisdiction_ocdid, []).append(labelled(person))
    return by_jurisdiction


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


# Matches `memberships.STATE_CHUNK_SIZE`; the sheet writes in the same blocks.
PEOPLE_CHUNK_SIZE = 2000

_PEOPLE_IN_STATE = """
    FROM people
    WHERE jurisdiction_ocdid LIKE %(prefix)s
"""

_PEOPLE_SHEET_ROWS = """
            SELECT jurisdiction_ocdid,
                   id::text     AS person_id,
                   name         AS person_name,
                   other_names  AS person_other_names,
                   emails       AS person_emails,
                   phones       AS person_phones,
                   urls         AS person_urls,
                   image        AS person_image,
                   cdn_image    AS person_cdn_image,
                   source_urls  AS person_source_urls,
                   updated_at   AS person_updated_at
"""


def _state_prefix(state: str) -> str:
    return f"ocd-jurisdiction/country:us/state:{state.lower()}%"


async def count_for_state(state: str) -> int:
    """How many rows `stream_for_state` will yield — `ensure_tab` sizes the grid from it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT count(*) {_PEOPLE_IN_STATE}", {"prefix": _state_prefix(state)}
        )
        row = await cur.fetchone()
    return row[0] if row else 0


async def stream_for_state(
    state: str, chunk_size: int = PEOPLE_CHUNK_SIZE
) -> AsyncGenerator[list[dict], None]:
    """Every person in a state, one row each, in chunks.

    Person-grained on purpose: this feeds the tab a curator scans for a near-miss *name*, and a
    person repeated once per seat is noise there. Who holds what is the memberships tab.

    Everyone we hold, including anyone with no membership at all — they are exactly the person
    about to be re-added under a slightly different spelling.

    Aliases are a contract with `core.sheet.people_rows.HEADERS`.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(name=f"people_sheet_{uuid.uuid4().hex}") as cur:
            await cur.execute(
                _PEOPLE_SHEET_ROWS + _PEOPLE_IN_STATE + " ORDER BY name, id",
                {"prefix": _state_prefix(state)},
            )
            while rows := await cur.fetchmany(chunk_size):
                columns = [column.name for column in cur.description or []]
                yield [dict(zip(columns, row)) for row in rows]


async def delete_person(person_id: str, user_id: str | None = None) -> str | None:
    """Returns the jurisdiction they were in, or None when there was no such person.

    Returned rather than discarded because the caller mirrors the removal outward, and once
    the row is gone there is nothing left to ask.

    Mints a `PEOPLE_EDIT` changeset, born published — the same shape `edit_published` uses for
    any other synchronous hand edit to the live roster. It used to mint none: the activity row
    carried `changeset_id=NULL`, which is what let a deletion through this route slip past
    step 9's changeset-scoped rollback surface with nothing to roll back from.

    `RETURNING name` too, because after the delete there is nobody left to name in the log.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM people WHERE id = %s RETURNING jurisdiction_ocdid, name",
            (person_id,),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        jurisdiction_ocdid, name = row

        changeset_id = make_id()
        await register_people_edit_changeset(
            changeset_id, jurisdiction_ocdid, user_id or SYSTEM_USER_ID
        )
        await record_change(
            cur,
            ActivityType.DELETE_PERSON,
            user_id,
            jurisdiction_ocdid,
            Change(entity_type=EntityType.PERSON, entity_id=person_id, subject=name),
            changeset_id=changeset_id,
        )
    return jurisdiction_ocdid


