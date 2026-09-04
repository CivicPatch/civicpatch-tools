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
from datetime import date, datetime, timezone
from typing import AsyncGenerator

from core.membership_label import derive_post_label
from core.post_derivation import DerivedMembership
from database import assertions, posts
from database.change_logs import record_change
from database.changesets import live_roster_changeset
from database.database import get_pool
from database.pipeline_runs import get_updated_at
from schemas.assertions import Assertion, AssertionKind, EntityType
from schemas.posts import AssignmentResult
from schemas.change_logs import (
    MEMBERSHIP_POST_FIELD,
    FieldChange,
    MembershipChangePayload,
)
from shared.utils.statuses import ChangeLogType

# The field a human can own, named once: it is compared in SQL below and asserted in Python.
LABEL_FIELD = "label"

LABEL_IS_HUMAN_SET = f"""COALESCE((
    SELECT assertions.kind = 'accept'
    FROM assertions
    WHERE assertions.entity_type = 'membership'
      AND assertions.entity_id = memberships.id
      AND assertions.field_path = '{LABEL_FIELD}'
    ORDER BY assertions.asserted_at DESC
    LIMIT 1
), false)"""


class UnknownPost(Exception):
    """The post id does not exist."""


class NothingToAssign(Exception):
    """They already hold that post under that label."""


async def _set_membership_roles(cur, membership_id: str, role_ids: list[str]) -> None:
    """Replace the roles the label named beyond the one defining the post.

    Wholesale, not merged: these are derived from the label, so the current scrape's answer is
    the whole answer and a role dropped from the page must not linger.
    """
    await cur.execute(
        "DELETE FROM membership_roles WHERE membership_id::text = %s", (membership_id,)
    )
    if not role_ids:
        return
    await cur.executemany(
        "INSERT INTO membership_roles (membership_id, role_id) VALUES (%s, %s) "
        "ON CONFLICT DO NOTHING",
        [(membership_id, role_id) for role_id in role_ids],
    )


async def upsert(
    cur,
    member: DerivedMembership,
    post_id: str,
    organization_id: str,
    last_seen_at,
    *,
    advances_last_seen: bool = True,
) -> str:
    """Seat one person, closing whatever else they held in this organization.

    Takes the `DerivedMembership` whole: five of the old twelve parameters were its fields,
    unpacked at the only caller and passed back one at a time.

    `advances_last_seen` is False when the publish read no source — a hand edit. A flag rather
    than a second function because it toggles one clause of one statement; splitting would mean
    two copies of this SQL, which is the drift the single statement exists to prevent. A new
    seat is still dated from `last_seen_at`; only the advance on an existing one is suppressed.

    `start_date` / `end_date` come off the record, via `DerivedMembership`. They used to be
    parameters nobody passed, so the source's term dates reached `people` and never the
    membership that is the tenure.
    """
    person_id = member.person_id
    await cur.execute(
        """
        UPDATE memberships SET closed_at = %s
        WHERE person_id = %s AND organization_id = %s
          AND closed_at IS NULL AND post_id <> %s
        """,
        (last_seen_at, person_id, organization_id, post_id),
    )

    await cur.execute(
        f"""
        INSERT INTO memberships
            (post_id, organization_id, person_id, designations, unmatched_text,
             source_labels, start_date, end_date, first_seen_at, last_seen_at, label)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (person_id, organization_id) WHERE closed_at IS NULL
        DO UPDATE SET
            -- Only a publish that read a source may advance this. A hand edit still dates a
            -- *new* seat (the INSERT above), but must not claim the source still lists an
            -- existing one.
            last_seen_at = CASE WHEN %s
                THEN GREATEST(memberships.last_seen_at, EXCLUDED.last_seen_at)
                ELSE memberships.last_seen_at END,
            designations = EXCLUDED.designations,
            unmatched_text = EXCLUDED.unmatched_text,
            source_labels = EXCLUDED.source_labels,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date,
            label = CASE WHEN {LABEL_IS_HUMAN_SET}
                         THEN memberships.label ELSE EXCLUDED.label END
        RETURNING id::text
        """,
        (
            post_id,
            organization_id,
            person_id,
            member.designations,
            member.unmatched_text,
            member.source_labels,
            member.start_date,
            member.end_date,
            last_seen_at,
            last_seen_at,
            member.label,
            advances_last_seen,
        ),
    )
    membership_id = (await cur.fetchone())[0]
    await _set_membership_roles(cur, membership_id, member.role_ids)
    return membership_id


async def advance_last_seen_at(cur, person_ids: list[str], last_seen_at) -> int:
    """Transaction time: we saw them, not a claim about their tenure. `GREATEST` so an
    out-of-order scrape cannot walk the clock backwards."""
    if not person_ids:
        return 0
    await cur.execute(
        """
        UPDATE memberships SET last_seen_at = GREATEST(last_seen_at, %s)
        WHERE person_id = ANY(%s) AND closed_at IS NULL
        """,
        (last_seen_at, person_ids),
    )
    return cur.rowcount


async def close_absent(
    cur, jurisdiction_ocdid: str, present_person_ids: list[str], closed_at
) -> int:
    """Close open memberships for anyone the scrape did not name.

    An empty roster closes nobody — that is a failed scrape, not a dissolved council.

    Untracked posts close too. `closed_at` is transaction time: it records that we stopped
    seeing someone, not a claim that they left. Whether anyone is asked to look at that is
    `posts.is_tracked`, and that gates the review queue, not the record.
    """
    if not present_person_ids:
        return 0

    await cur.execute(
        """
        UPDATE memberships m SET closed_at = %s
        FROM posts p
        WHERE m.post_id = p.id
          AND p.jurisdiction_ocdid = %s
          AND m.closed_at IS NULL
          AND m.person_id <> ALL(%s)
        """,
        (closed_at, jurisdiction_ocdid, present_person_ids),
    )
    return cur.rowcount


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
               m.source_labels, m.designations, m.unmatched_text,
               p.role_id, p.division_ocdid,
               r.label AS role_label
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        JOIN people pe ON pe.id = m.person_id
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
            "post_label": derive_post_label(
                row["role_label"], row["division_ocdid"]
            ),
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
        "post_label": derive_post_label(
            row["role_label"], row["post_division_ocdid"]
        ),
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
                   m.source_labels  AS membership_source_labels
            FROM memberships m
            JOIN posts p ON p.id = m.post_id
            JOIN people pe ON pe.id = m.person_id
            JOIN roles r ON r.id = p.role_id
            WHERE p.jurisdiction_ocdid LIKE %(prefix)s
            ORDER BY p.jurisdiction_ocdid, pe.name, pe.id, m.first_seen_at
"""


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
                yield [
                    _with_post_label(dict(zip(columns, row))) for row in rows
                ]


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
    CROSS JOIN LATERAL unnest(m.unmatched_text) AS term
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
                   SELECT l FROM unnest(m.source_labels) AS l
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


async def unmatched_text(limit: int, offset: int) -> tuple[int, list[dict]]:
    """One page of triage terms, and how many there are in total.

    Counted separately rather than with a window function so the total survives an `offset`
    past the end — a window has no row to read the count from, and the pager would collapse
    to zero pages.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await _count_triage_terms(cur), await _triage_page(cur, limit, offset)


async def open_by_jurisdiction(
    cur, jurisdiction_ocdids: list[str]
) -> dict[str, list[dict]]:
    """Open memberships with the seat they sit on, grouped by jurisdiction.

    Takes a list because the review queue asks for hundreds at once; one query per jurisdiction
    was the whole cost of ordering it.
    """
    if not jurisdiction_ocdids:
        return {}
    await cur.execute(
        """
        SELECT p.jurisdiction_ocdid, m.person_id::text, m.post_id::text,
               p.role_id, p.division_ocdid, p._is_tracked AS is_tracked,
               r.label AS role_label
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        JOIN roles r ON r.id = p.role_id
        WHERE p.jurisdiction_ocdid = ANY(%s) AND m.closed_at IS NULL
        """,
        (jurisdiction_ocdids,),
    )
    columns = [column.name for column in cur.description or []]
    grouped: dict[str, list[dict]] = {ocdid: [] for ocdid in jurisdiction_ocdids}
    for row in await cur.fetchall():
        held = dict(zip(columns, row))
        grouped[held.pop("jurisdiction_ocdid")].append(held)
    return grouped


async def set_label(
    cur, membership_id: str, label: str | None, user_id: str | None = None
) -> None:
    """Name this person's post, or clear it back to the derived guess.

    `user_id` records that a human owns the value, which is what stops the next scrape
    overwriting it — writing the column without that is how a reviewer's choice silently
    reverts. Omitted only where the caller is not a person.
    """
    await cur.execute(
        "UPDATE memberships SET label = %s WHERE id::text = %s",
        (label, membership_id),
    )
    if user_id is None:
        return
    if label is None:
        await assertions.withdraw(
            cur, EntityType.MEMBERSHIP, membership_id, LABEL_FIELD
        )
        return
    await assertions.upsert(
        cur,
        Assertion(
            entity_type=EntityType.MEMBERSHIP,
            entity_id=membership_id,
            field_path=LABEL_FIELD,
            kind=AssertionKind.ACCEPT,
            value=label,
        ),
        user_id,
    )


async def open_for_person(cur, person_id: str, organization_id: str) -> dict | None:
    """This person's current post in this body. At most one row —
    `memberships_one_open_per_organization` enforces it."""
    await cur.execute(
        """
        SELECT id::text, post_id::text, label, designations, unmatched_text
        FROM memberships
        WHERE person_id = %s AND organization_id = %s AND closed_at IS NULL
        """,
        (person_id, organization_id),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return dict(zip([c.name for c in cur.description or []], row))


async def _person_name(cur, person_id: str) -> str:
    """What a reader recognises the person by. Ids do not render in an activity feed."""
    await cur.execute("SELECT name FROM people WHERE id = %s", (person_id,))
    row = await cur.fetchone()
    return (row[0] if row else None) or person_id


async def assign(
    person_id: str, post_id: str, label: str | None, user_id: str | None = None
) -> AssignmentResult:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        post = await posts.get(cur, post_id)
        if post is None:
            raise UnknownPost(post_id)

        # Same changeset, same date. The seat is dated by the changeset this edit is filed
        # under — the live roster's — so a hand edit cannot advance `last_seen_at`: `upsert`
        # takes GREATEST, and that date is already the seat's. Nobody read a source here.
        changeset_id = await live_roster_changeset(cur, post.jurisdiction_ocdid)
        seen_at = (
            await get_updated_at(cur, changeset_id)
            if changeset_id
            # Nothing published here yet, so there is no changeset to date from.
            else datetime.now(timezone.utc)
        )

        organization_id = post.organization_id
        current = await open_for_person(cur, person_id, organization_id)

        if current and current["post_id"] == post_id:
            if (current["label"] or None) == (label or None):
                raise NothingToAssign(post_id)
            membership_id = current["id"]
            change = FieldChange(
                field=LABEL_FIELD, before=current["label"], after=label
            )
        else:
            moved_from = current["post_id"] if current else None
            membership_id = await upsert(
                # A human assigning a seat states only who and where — the label follows
                # below, and the source's term dates are not theirs to invent.
                cur,
                DerivedMembership(person_id=person_id),
                post_id,
                organization_id,
                seen_at,
            )
            change = FieldChange(
                field=MEMBERSHIP_POST_FIELD, before=moved_from, after=post_id
            )

        await set_label(cur, membership_id, label, user_id)

        await record_change(
            cur,
            ChangeLogType.ASSIGN_MEMBERSHIP,
            user_id,
            post.jurisdiction_ocdid,
            MembershipChangePayload(
                membership_id=membership_id,
                person_id=person_id,
                person_name=await _person_name(cur, person_id),
                post_id=post_id,
                role_id=post.role_id,
                label=label or post.label,
                fields=[change],
            ),
            # So the edit lands on the live roster's timeline entry rather than nowhere.
            changeset_id=changeset_id,
        )
        return AssignmentResult(
            membership_id=membership_id,
            jurisdiction_ocdid=post.jurisdiction_ocdid,
            change=change,
        )
