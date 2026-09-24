"""Database queries for `memberships` — a person holding a post over time.

Three cases, and they are the whole model:

  found on the same post       advance `last_seen_at`
  found on a different post    close the old membership, open a new one
  not found at all             close it

Closing rather than moving preserves history: a move leaves a closed row with its own window,
which is what the roster timeline reads. One *open* membership per person per body.

`closed_at` is ours and `end_date` is the source's — disappearing from a page says someone is
gone, not when they went.
"""

import uuid
from datetime import date
from typing import AsyncGenerator

from core.membership_label import derive_post_label
from core.membership_proposal import ExistingMembership, MembershipPost
from core.projection.memberships import MEMBERSHIP_LABEL_FIELD
from database import assertions, posts
from database.activity import record_change
from database.changesets import live_roster_changeset
from database.database import get_pool
from database.projection import rebuild_from_facts
from database.users import SYSTEM_USER_ID
from schemas.activity import (
    MEMBERSHIP_POST_FIELD,
    Change,
    FieldChange,
)
from schemas.assertions import (
    DefaultNote,
    Assertion,
    AssertionKind,
    EntityType,
    Source,
)
from shared.utils.membership_ids import membership_id
from shared.utils.statuses import ActivityType


async def list_for_jurisdiction(
    cur, jurisdiction_ocdid: str, as_of: date | None = None
) -> list[dict]:
    await cur.execute(
        """
        SELECT m.id::text, m.person_id::text, m.post_id::text, m.label,
               m.start_date, m.end_date,
               -- The interval, both ends. `closed_at IS NULL` is an open membership, so the
               -- range is half-open and a reader can draw it without inferring the end from a
               -- sighting. This is the pair `as_of` filters on below, so a row explains why
               -- it was included.
               m.first_seen_at, m.closed_at, m.last_seen_at,
               pe.name AS person_name,
               membership_source_labels(m.sources) AS source_labels,
               m.designations, m.meta_unmatched_text,
               p.role_id, p.division_ocdid,
               p.organization_id::text, o.name AS organization_name,
               r.label AS role_label
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        JOIN people pe ON pe.id = m.person_id
        JOIN organizations o ON o.id = p.organization_id
        JOIN roles r ON r.id = p.role_id
        WHERE p.jurisdiction_ocdid = %(jurisdiction_ocdid)s
          AND m.first_seen_at < COALESCE(%(as_of)s::date + 1, now())
          AND (m.closed_at IS NULL OR m.closed_at >= COALESCE(%(as_of)s::date + 1, now()))
        ORDER BY pe.name, p.role_id
        """,
        {"jurisdiction_ocdid": jurisdiction_ocdid, "as_of": as_of},
    )
    columns = [column.name for column in cur.description or []]
    rows = [dict(zip(columns, row)) for row in await cur.fetchall()]
    return [
        {
            **row,
            "post_label": derive_post_label(row["role_label"], row["division_ocdid"]),
        }
        for row in rows
    ]


async def list_by_person(
    jurisdiction_ocdid: str, as_of: date | None = None
) -> list[dict]:
    """The roster by person rather than by post. `as_of` is None for now."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await list_for_jurisdiction(cur, jurisdiction_ocdid, as_of)


# The same shape `people._scope` and `posts.list_page_for_state` build. Written out a third
# time rather than shared: lifting it would mean editing both of those, and this change is
# otherwise purely additive.
_STATE_PREFIX = "ocd-jurisdiction/country:us/state:{state}%"


def _with_post_label(row: dict) -> dict:
    """`posts.label` was dropped by 148, so the seat's name is composed on read.

    `role_label` goes: it is here only to compose `post_label`, and a column no sheet header
    names would just invite a second source of truth for the same wording.
    """
    composed = {
        **row,
        "post_label": derive_post_label(row["role_label"], row["post_division_ocdid"]),
    }
    del composed["role_label"]
    return composed


# How many rows a stream hands back at a time. Matches the sheet's write chunk, so a chunk is
# read, written and dropped rather than the whole state being held to write it in pieces.
STATE_CHUNK_SIZE = 2000

# The `FROM` both the stream and the count share, so the count cannot describe a different set.
# `people` and `roles` are left out of it: both joins are on NOT NULL foreign keys, so neither
# can drop a row, and counting without them is cheaper.
_STATE_POPULATION = """
    FROM memberships m
    JOIN posts p ON p.id = m.post_id
    WHERE p.jurisdiction_ocdid LIKE %(prefix)s
"""

_STATE_ROWS = """
            SELECT p.jurisdiction_ocdid,
                   pe.id::text      AS person_id,
                   pe.name          AS person_name,
                   pe.other_names   AS person_other_names,
                   pe.emails        AS person_emails,
                   pe.phones        AS person_phones,
                   pe.urls          AS person_urls,
                   pe.image         AS person_image,
                   pe.cdn_image     AS person_cdn_image,
                   pe.source_urls   AS person_source_urls,
                   pe.updated_at    AS person_updated_at,
                   p.id::text       AS post_id,
                   p.role_id        AS post_role_id,
                   p.division_ocdid AS post_division_ocdid,
                   r.label          AS role_label,
                   m.id::text       AS membership_id,
                   m.label          AS membership_label,
                   m.start_date     AS membership_start_date,
                   m.end_date       AS membership_end_date,
                   m.first_seen_at  AS membership_first_seen_at,
                   m.last_seen_at   AS membership_last_seen_at,
                   m.closed_at      AS membership_closed_at,
                   membership_source_labels(m.sources) AS membership_source_labels
            FROM memberships m
            JOIN posts p ON p.id = m.post_id
            JOIN people pe ON pe.id = m.person_id
            JOIN roles r ON r.id = p.role_id
            WHERE p.jurisdiction_ocdid LIKE %(prefix)s
            ORDER BY p.jurisdiction_ocdid, pe.name, pe.id, m.first_seen_at
"""


async def jurisdictions_with_rosters(state: str) -> list[str]:
    """Every jurisdiction in this state that open-data should hold a file for.

    An open membership is the test, because that is what `get_roster` renders. A jurisdiction
    whose last seat closed keeps its file until something rewrites it — deleting from open-data
    is a separate decision, and not one a backstop should take.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT DISTINCT p.jurisdiction_ocdid
            FROM memberships m
            JOIN posts p ON p.id = m.post_id
            WHERE p.jurisdiction_ocdid LIKE %(prefix)s
              AND m.closed_at IS NULL
            ORDER BY p.jurisdiction_ocdid
            """,
            {"prefix": _STATE_PREFIX.format(state=state.lower())},
        )
        return [row[0] for row in await cur.fetchall()]


async def count_for_state(state: str) -> int:
    """How many rows `stream_for_state` will yield.

    Asked separately because `ensure_tab` has to size the sheet's grid before the first write —
    `values.update` refuses a range past the grid — and a generator cannot say how long it is
    until it is exhausted.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"SELECT count(*) {_STATE_POPULATION}",
            {"prefix": _STATE_PREFIX.format(state=state.lower())},
        )
        row = await cur.fetchone()
    return row[0] if row else 0


async def stream_for_state(
    state: str, chunk_size: int = STATE_CHUNK_SIZE
) -> AsyncGenerator[list[dict], None]:
    """Every membership in a state, open and closed, one row per membership, in chunks.

    No `as_of` window, unlike `list_for_jurisdiction`: the sheet carries the whole history, so a
    closed row is the point rather than something to filter out. That is also what separates it
    from `people.get_roster`, whose `PERSON_MEMBERSHIPS` projection is `closed_at IS NULL` and
    cannot reach history at all.

    **Server-side cursor.** psycopg buffers a whole result set client-side otherwise, and a state
    costs about 3.5 KB a row — 20 MB for Texas today and far more at national coverage, times
    however many states are syncing at once, since each is its own workflow. A named cursor
    holds one chunk.

    **The aliases are a contract with `core.sheet.people_rows.HEADERS`** — that module
    reads rows by these names, so renaming one here empties a cell rather than raising.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        # Unique per call: two streams sharing a connection would otherwise collide on the name.
        async with conn.cursor(name=f"roster_sheet_{uuid.uuid4().hex}") as cur:
            await cur.execute(
                _STATE_ROWS, {"prefix": _STATE_PREFIX.format(state=state.lower())}
            )
            while rows := await cur.fetchmany(chunk_size):
                columns = [column.name for column in cur.description or []]
                yield [_with_post_label(dict(zip(columns, row))) for row in rows]


async def list_for_state(state: str) -> list[dict]:
    """The whole state at once. Drains `stream_for_state` rather than running its own query, so
    there is one SQL string and the two cannot describe different rows."""
    rows: list[dict] = []
    async for chunk in stream_for_state(state):
        rows.extend(chunk)
    return rows


# Shared by the count and the page so the two cannot describe different sets.
_TRIAGE_POPULATION = """
    FROM memberships m
    JOIN posts p ON p.id = m.post_id
    CROSS JOIN LATERAL unnest(m.meta_unmatched_text) AS term
    WHERE m.closed_at IS NULL
    GROUP BY lower(term)
"""


async def _count_triage_terms(cur) -> int:
    await cur.execute(f"SELECT count(*) FROM (SELECT 1 {_TRIAGE_POPULATION}) t")
    row = await cur.fetchone()
    return row[0] if row is not None else 0


async def _triage_page(cur, limit: int, offset: int) -> list[dict]:
    await cur.execute(
        f"""
        SELECT mode() WITHIN GROUP (ORDER BY term) AS text,
               count(*) AS occurrences,
               count(DISTINCT p.jurisdiction_ocdid) AS jurisdictions,
               (array_agg(DISTINCT p.jurisdiction_ocdid
                          ORDER BY p.jurisdiction_ocdid))[1:3] AS examples,
               -- The one label the term came out of, not the whole concatenation. Storing
               -- the parts is what makes this answerable at all.
               mode() WITHIN GROUP (ORDER BY (
                   SELECT l FROM unnest(membership_source_labels(m.sources)) AS l
                   WHERE strpos(lower(l), lower(term)) > 0 LIMIT 1
               )) AS example_label
        {_TRIAGE_POPULATION}
        ORDER BY count(DISTINCT p.jurisdiction_ocdid) DESC, count(*) DESC, lower(term)
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def meta_unmatched_text(limit: int, offset: int) -> tuple[int, list[dict]]:
    """One page of triage terms, and how many there are in total.

    Counted separately rather than with a window function so the total survives an `offset`
    past the end — a window has no row to read the count from, and the pager would collapse
    to zero pages.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await _count_triage_terms(cur), await _triage_page(cur, limit, offset)


async def open_memberships(
    cur, jurisdiction_ocdids: list[str]
) -> list[ExistingMembership]:
    """Every open membership in these jurisdictions, with its post's role and division."""
    if not jurisdiction_ocdids:
        return []
    await cur.execute(
        """
        SELECT m.id::text, p.jurisdiction_ocdid, m.person_id::text, m.organization_id::text,
               m.label, m.post_id::text, p.role_id, r.label, p.division_ocdid, p.meta_is_tracked
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        JOIN roles r ON r.id = p.role_id
        WHERE p.jurisdiction_ocdid = ANY(%s) AND m.closed_at IS NULL
        """,
        (jurisdiction_ocdids,),
    )
    rows = await cur.fetchall()
    names = await posts.asserted_labels(cur, [row[5] for row in rows])
    return [
        ExistingMembership(
            id=membership_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            person_id=person_id,
            organization_id=organization_id,
            membership_label=membership_label,
            post=MembershipPost(
                id=post_id,
                role_id=role_id,
                role_label=role_label,
                division_ocdid=division_ocdid,
                label=names.get(post_id)
                or derive_post_label(role_label, division_ocdid),
                meta_is_tracked=meta_is_tracked,
            ),
        )
        for (
            membership_id,
            jurisdiction_ocdid,
            person_id,
            organization_id,
            membership_label,
            post_id,
            role_id,
            role_label,
            division_ocdid,
            meta_is_tracked,
        ) in rows
    ]


async def _assert(
    cur,
    membership_id: str,
    field_path: str,
    kind: AssertionKind,
    user_id: str,
    reason: str | None,
    changeset_id: str | None,
) -> str:
    return await assertions.upsert(
        cur,
        Assertion(
            entity_type=EntityType.MEMBERSHIP,
            entity_id=membership_id,
            field_path=field_path,
            kind=kind,
            value=True,
            sources=[Source(note=reason or DefaultNote.NO_REASON)],
            changeset_id=changeset_id,
        ),
        user_id,
    )


async def set_membership_label(
    cur,
    membership_id: str,
    label: str | None,
    user_id: str,
    changeset_id: str | None = None,
) -> None:
    """Name this person's post, or clear it back to the derived guess.

    The claim is the whole value: the row is rewritten from the facts at the next rebuild, so
    a column written here would be a copy the next publish disagrees with.
    """
    if label is None:
        # An ordinary withdrawal, not a rollback's — withdrawn_by_changeset_id stays NULL.
        await assertions.withdraw(
            cur,
            EntityType.MEMBERSHIP,
            membership_id,
            MEMBERSHIP_LABEL_FIELD,
            AssertionKind.ACCEPT,
            user_id,
        )
        return
    await assertions.upsert(
        cur,
        Assertion(
            entity_type=EntityType.MEMBERSHIP,
            entity_id=membership_id,
            field_path=MEMBERSHIP_LABEL_FIELD,
            kind=AssertionKind.ACCEPT,
            value=label,
            sources=[Source(note=DefaultNote.LABEL_SET)],
            changeset_id=changeset_id,
        ),
        user_id,
    )


async def open_memberships_for_persons(cur, person_ids: list[str]) -> list[dict]:
    """Every open membership these people hold: the post it is in, and the row id the
    proposal layer still looks label assertions up by (step 2).

    Person id, not entity id: the editor's per-person payload carries neither. One person can
    hold more than one open membership, so this is a row per membership, not per person.
    """
    if not person_ids:
        return []
    await cur.execute(
        "SELECT id::text, person_id::text, post_id::text FROM memberships "
        "WHERE person_id = ANY(%s) AND closed_at IS NULL",
        (person_ids,),
    )
    return [
        {"id": row[0], "person_id": row[1], "post_id": row[2]}
        for row in await cur.fetchall()
    ]


async def _person_name(cur, person_id: str) -> str:
    """What a reader recognises the person by. Ids do not render in an activity feed."""
    await cur.execute("SELECT name FROM people WHERE id = %s", (person_id,))
    row = await cur.fetchone()
    return (row[0] if row else None) or person_id
