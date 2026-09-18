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

import json
import uuid
from datetime import date, datetime, timezone
from typing import AsyncGenerator

from core.membership_label import derive_post_label
from core.membership_proposal import (
    ExistingMembership,
    MembershipPost,
    ids_by_person_and_organization,
)
from core.post_derivation import DerivedMembership, MembershipBinding
from database import assertions, posts
from database.assertions import LATEST_FIRST
from database.activity import record_change
from database.changesets import get_updated_at, live_roster_changeset
from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType, Source
from schemas.activity import (
    MEMBERSHIP_POST_FIELD,
    Change,
    FieldChange,
)
from schemas.posts import AssignmentResult, MembershipRemovalAssertion
from shared.utils.statuses import ActivityType

# The field a human can own, named once: it is compared in SQL below and asserted in Python.
LABEL_FIELD = "label"

# Sentinel field_path for "this membership never held" (189) — a reject assertion about the
# row itself, not a field of it. `field_path` is NOT NULL and a whole-row claim isn't a field,
# so this is the one-time ugliness the plan named rather than solved: a `post_id` reject was
# considered and is structurally impossible (`NOT_REJECTABLE`), and a new `kind` would have
# meant teaching the fold a third value everywhere it currently only expects two.
EXISTENCE_FIELD = "exists"
# The claim "stop listing this membership": accepted on the membership, applied at publish by
# closing it. Not a claim about the term — `closed_at` is ours, `end_date` is the source's.
# A claim rather than a bare write so it can be withdrawn, and so rollback re-derives without a
# special case (see the plan's `published state = f(evidence, claims)`).
CLOSED_FIELD = "closed_at"
# The value carried by every retraction claim. Fixed and arbitrary — a reject's dedup key
# includes its value, so retract/reinstate always targets the same (entity, field, value) row
# rather than accumulating a new one each cycle.
_RETRACTED = True

# withdrawn_at IS NULL, added 189: without it this found a withdrawn label assertion just as
# readily as a live one, since the ORDER BY has no opinion on withdrawal — so clearing a label
# back to derived (set_label's withdraw call) had no effect here, and the very next scrape
# would still be refused the field it was just supposed to get back.
LABEL_IS_HUMAN_SET = f"""COALESCE((
    SELECT assertions.kind = 'accept'
    FROM assertions
    WHERE assertions.entity_type = 'membership'
      AND assertions.entity_id = memberships.id
      AND assertions.field_path = '{LABEL_FIELD}'
      AND assertions.withdrawn_at IS NULL
    {LATEST_FIRST}
    LIMIT 1
), false)"""


class UnknownPost(Exception):
    """The post id does not exist."""


class NothingToAssign(Exception):
    """They already hold that post under that label."""


_CLOSE_MOVED_MEMBERSHIPS = """
    UPDATE memberships SET closed_at = %s
    WHERE person_id = %s AND organization_id = %s
      AND closed_at IS NULL AND post_id <> %s
"""

# Only a publish that read a source advances `last_seen_at`; a hand edit still dates a new one.
_UPSERT_OPEN_MEMBERSHIPS = f"""
    INSERT INTO memberships
        (post_id, organization_id, person_id, designations, meta_unmatched_text,
         sources, start_date, end_date, first_seen_at, last_seen_at, label)
    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
    ON CONFLICT (person_id, organization_id) WHERE closed_at IS NULL
    DO UPDATE SET
        last_seen_at = CASE WHEN %s
            THEN GREATEST(memberships.last_seen_at, EXCLUDED.last_seen_at)
            ELSE memberships.last_seen_at END,
        designations = EXCLUDED.designations,
        meta_unmatched_text = EXCLUDED.meta_unmatched_text,
        sources = EXCLUDED.sources,
        start_date = EXCLUDED.start_date,
        end_date = EXCLUDED.end_date,
        label = CASE WHEN {LABEL_IS_HUMAN_SET}
                     THEN memberships.label ELSE EXCLUDED.label END
"""

_DELETE_MEMBERSHIP_ROLES = "DELETE FROM membership_roles WHERE membership_id::text = %s"

_INSERT_MEMBERSHIP_ROLE = """
    INSERT INTO membership_roles (membership_id, role_id) VALUES (%s, %s)
    ON CONFLICT DO NOTHING
"""


def _upsert_params(binding: MembershipBinding, last_seen_at, advances_last_seen: bool) -> tuple:
    member = binding.member
    return (
        binding.post_id,
        binding.organization_id,
        member.person_id,
        member.designations,
        member.meta_unmatched_text,
        json.dumps([source.model_dump() for source in member.sources]),
        member.start_date,
        member.end_date,
        last_seen_at,
        last_seen_at,
        member.membership_label,
        advances_last_seen,
    )


def _open_membership_key(binding: MembershipBinding) -> tuple[str, str]:
    return (binding.member.person_id, binding.organization_id)


async def close_moved_memberships(cur, bindings: list[MembershipBinding], closed_at) -> None:
    """Close each person's open membership in the organization when it is on a different post."""
    await cur.executemany(
        _CLOSE_MOVED_MEMBERSHIPS,
        [
            (closed_at, binding.member.person_id, binding.organization_id, binding.post_id)
            for binding in bindings
        ],
    )


async def upsert_open_memberships(
    cur, bindings: list[MembershipBinding], last_seen_at, advances_last_seen: bool
) -> None:
    """Open each membership, or refresh the open one; a human-set label is kept."""
    await cur.executemany(
        _UPSERT_OPEN_MEMBERSHIPS,
        [_upsert_params(binding, last_seen_at, advances_last_seen) for binding in bindings],
    )


async def replace_membership_roles(
    cur, bindings: list[MembershipBinding], membership_ids: dict[tuple[str, str], str]
) -> None:
    """Replace the open memberships' extra roles (beyond the post's own) with the latest label's."""
    await cur.executemany(
        _DELETE_MEMBERSHIP_ROLES, [(membership_ids[_open_membership_key(binding)],) for binding in bindings]
    )
    await cur.executemany(
        _INSERT_MEMBERSHIP_ROLE,
        [
            (membership_ids[_open_membership_key(binding)], role_id)
            for binding in bindings
            for role_id in binding.member.role_ids
        ],
    )


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


def removal_claimed(claim: dict) -> MembershipRemovalAssertion:
    """Which of the three a membership's live claims amount to. One reading, so publish and the
    editor cannot disagree about what somebody chose."""
    if claim.get(EXISTENCE_FIELD, {}).get(AssertionKind.REJECT):
        return MembershipRemovalAssertion.NEVER_HELD
    if claim.get(CLOSED_FIELD, {}).get(AssertionKind.ACCEPT):
        return MembershipRemovalAssertion.CLOSED
    return MembershipRemovalAssertion.NONE


async def close_claimed(cur, jurisdiction_ocdid: str, closed_at) -> int:
    """Close every open membership somebody said to stop carrying, and every one they said never
    held.

    Publish's other close (`close_absent`) is an inference from the source; this one is somebody's
    claim, so it runs whatever the scrape covered.
    """
    held = await open_memberships(cur, [jurisdiction_ocdid])
    if not held:
        return 0
    claims = await assertions.asserted_values(
        cur, EntityType.MEMBERSHIP, [membership.id for membership in held]
    )
    ended = [
        membership.id
        for membership in held
        if removal_claimed(claims.get(membership.id, {})) is not MembershipRemovalAssertion.NONE
    ]
    if not ended:
        return 0
    await cur.execute(
        "UPDATE memberships SET closed_at = %s WHERE id::text = ANY(%s) AND closed_at IS NULL",
        (closed_at, ended),
    )
    return cur.rowcount


async def close_for_people_rejected_here(cur, jurisdiction_ocdid: str, closed_at) -> int:
    """Close every membership of a person somebody said is a member of nothing here.

    The other half of the fork a reviewer faces: closing one membership says stop listing them in
    that organization, this says the record does not belong to this jurisdiction at all. The person
    row survives either way, because deleting it is its own act and the only irreversible one.
    """
    held = await open_memberships(cur, [jurisdiction_ocdid])
    if not held:
        return 0
    claims = await assertions.asserted_values(
        cur, EntityType.PERSON, list({membership.person_id for membership in held})
    )
    rejected = [
        person_id
        for person_id in {membership.person_id for membership in held}
        if claims.get(person_id, {}).get(EXISTENCE_FIELD, {}).get(AssertionKind.REJECT)
    ]
    return await close_for_people(cur, jurisdiction_ocdid, rejected, closed_at)


async def close_for_people(
    cur, jurisdiction_ocdid: str, person_ids: list[str], closed_at
) -> int:
    """Close every open membership these people hold here."""
    if not person_ids:
        return 0
    await cur.execute(
        """
        UPDATE memberships SET closed_at = %s
        WHERE person_id::text = ANY(%s) AND closed_at IS NULL
          AND post_id IN (SELECT id FROM posts WHERE jurisdiction_ocdid = %s)
        """,
        (closed_at, person_ids, jurisdiction_ocdid),
    )
    return cur.rowcount


async def close_absent(
    cur, organization_id: str, present_person_ids: list[str], closed_at
) -> int:
    if not present_person_ids:
        return 0

    # No join: `memberships.organization_id` is the scope, and an organization belongs to one
    # jurisdiction by construction.
    await cur.execute(
        """
        UPDATE memberships SET closed_at = %s
        WHERE organization_id = %s
          AND closed_at IS NULL
          AND person_id <> ALL(%s)
        """,
        (closed_at, organization_id, present_person_ids),
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
    """The roster by person rather than by post, each membership carrying whichever removal
    somebody has claimed about it. `as_of` is None for now.

    The claims ride along because the editor offers them as one exclusive choice: without them the
    screen would have to guess which button is already chosen, or ask per row. `not_a_member` is a
    claim about the person, so it repeats on each of their rows.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await list_for_jurisdiction(cur, jurisdiction_ocdid, as_of)
        claims = await assertions.asserted_values(
            cur, EntityType.MEMBERSHIP, [row["id"] for row in rows]
        )
        person_claims = await assertions.asserted_values(
            cur, EntityType.PERSON, list({row["person_id"] for row in rows})
        )
    return [
        {
            **row,
            "removal_assertion": removal_claimed(claims.get(row["id"], {})).value,
            "not_a_member": bool(
                person_claims.get(row["person_id"], {})
                .get(EXISTENCE_FIELD, {})
                .get(AssertionKind.REJECT)
            ),
        }
        for row in rows
    ]


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


async def open_memberships(cur, jurisdiction_ocdids: list[str]) -> list[ExistingMembership]:
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
                label=names.get(post_id) or derive_post_label(role_label, division_ocdid),
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
            changeset_id=changeset_id,
            sources=[Source(note=reason)] if reason else [],
        ),
        user_id,
    )


async def assert_closed_at(
    cur,
    membership_id: str,
    user_id: str,
    reason: str | None = None,
    changeset_id: str | None = None,
) -> str:
    """Somebody says to stop carrying this membership. Publish applies it (`close_claimed`);
    withdrawing it and publishing again re-derives the membership as though it had never been made.

    Not `end_date`: that is the source's claim about the term, and this one is ours about the
    record, the same split `closed_at` itself makes."""
    return await _assert(
        cur, membership_id, CLOSED_FIELD, AssertionKind.ACCEPT, user_id, reason, changeset_id
    )


async def withdraw_closed_at(cur, membership_id: str, user_id: str) -> int:
    return await assertions.withdraw(
        cur, EntityType.MEMBERSHIP, membership_id, CLOSED_FIELD, AssertionKind.ACCEPT, user_id
    )


async def set_label(
    cur,
    membership_id: str,
    label: str | None,
    user_id: str | None = None,
    changeset_id: str | None = None,
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
        # An ordinary withdrawal, not a rollback's — withdrawn_by_changeset_id stays NULL.
        await assertions.withdraw(
            cur, EntityType.MEMBERSHIP, membership_id, LABEL_FIELD, AssertionKind.ACCEPT, user_id
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
            changeset_id=changeset_id,
        ),
        user_id,
    )


async def retract(
    cur,
    membership_id: str,
    user_id: str,
    reason: str | None = None,
    changeset_id: str | None = None,
) -> str:
    """Say this membership never held — the moderation half of `EXISTENCE_FIELD`. Returns the
    claim's id.

    An ordinary reject assertion, entity_type='membership': `IS_ON_THE_ROSTER` excludes anyone
    with a live one, but the membership row, its `first_seen_at`, and the post it pointed at
    all survive — this is reversible by `reinstate`, unlike closing (`closed_at`) or deleting
    the row, neither of which this is.

    `reason`, when given, rides as `sources` — the same "phoned the clerk" mechanism every
    other assertion already has, rather than a new column just for this one.
    """
    return await assertions.upsert(
        cur,
        Assertion(
            entity_type=EntityType.MEMBERSHIP,
            entity_id=membership_id,
            field_path=EXISTENCE_FIELD,
            kind=AssertionKind.REJECT,
            value=_RETRACTED,
            sources=[Source(note=reason)] if reason else [],
            changeset_id=changeset_id,
        ),
        user_id,
    )


async def reinstate(cur, membership_id: str, user_id: str) -> int:
    """Undo the most recent `retract` on this membership — an ASSERT, undone by WITHDRAW, same
    as every other claim. Returns how many rows went — 0 if nothing here is currently
    retracted."""
    return await assertions.withdraw(
        cur, EntityType.MEMBERSHIP, membership_id, EXISTENCE_FIELD, AssertionKind.REJECT, user_id
    )


async def open_membership_ids_for_persons(cur, person_ids: list[str]) -> list[dict]:
    """Every open membership id for these people, to look up label assertions by.

    Person id, not entity id: `assertions` is keyed on `membership.id`, which the editor's
    per-person payload never otherwise carries. One person can hold more than one open
    membership (`memberships_one_open_per_organization` is per organization, not per
    person), so this returns a row per membership rather than one per person.
    """
    if not person_ids:
        return []
    await cur.execute(
        "SELECT id::text, person_id::text FROM memberships "
        "WHERE person_id = ANY(%s) AND closed_at IS NULL",
        (person_ids,),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def _person_name(cur, person_id: str) -> str:
    """What a reader recognises the person by. Ids do not render in an activity feed."""
    await cur.execute("SELECT name FROM people WHERE id = %s", (person_id,))
    row = await cur.fetchone()
    return (row[0] if row else None) or person_id


async def assign(
    person_id: str,
    post_id: str,
    label: str | None,
    user_id: str | None = None,
    changeset_id: str | None = None,
) -> AssignmentResult:
    """Assign a person to a post, direct and unasserted — a scrape stays free to move or end
    this membership again.

    `changeset_id`, when given, is the caller's own in-progress review — the activity entry and
    any label assertion are filed under it instead of the live roster's, so a pick made mid-
    review shows up as part of that review rather than as an unrelated jurisdiction edit.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        post = await posts.get(cur, post_id)
        if post is None:
            raise UnknownPost(post_id)

        # Same changeset, same date. The seat is dated by the changeset this edit is filed
        # under — so a hand edit cannot advance `last_seen_at`: `upsert_open_memberships` takes GREATEST, and
        # that date is already the seat's. Nobody read a source here.
        changeset_id = changeset_id or await live_roster_changeset(cur, post.jurisdiction_ocdid)
        seen_at = (
            await get_updated_at(cur, changeset_id)
            if changeset_id
            # Nothing published here yet, so there is no changeset to date from.
            else datetime.now(timezone.utc)
        )

        organization_id = post.organization_id
        held = await open_memberships(cur, [post.jurisdiction_ocdid])
        current = next(
            (
                membership
                for membership in held
                if membership.person_id == person_id and membership.organization_id == organization_id
            ),
            None,
        )

        if current and current.post.id == post_id:
            if (current.membership_label or None) == (label or None):
                raise NothingToAssign(post_id)
            membership_id = current.id
            change = FieldChange(
                field=LABEL_FIELD, before=current.membership_label, after=label
            )
        else:
            moved_from = current.post.id if current else None
            # A human states only who and where — the label follows below, and the source's
            # term dates are not theirs to invent.
            bindings = [
                MembershipBinding(
                    member=DerivedMembership(person_id=person_id),
                    organization_id=organization_id,
                    post_id=post_id,
                )
            ]
            await close_moved_memberships(cur, bindings, seen_at)
            await upsert_open_memberships(cur, bindings, seen_at, advances_last_seen=True)
            membership_ids = ids_by_person_and_organization(
                await open_memberships(cur, [post.jurisdiction_ocdid])
            )
            await replace_membership_roles(cur, bindings, membership_ids)
            membership_id = membership_ids[(person_id, organization_id)]
            change = FieldChange(
                field=MEMBERSHIP_POST_FIELD, before=moved_from, after=post_id
            )

        await set_label(cur, membership_id, label, user_id, changeset_id)

        await record_change(
            cur,
            ActivityType.ASSIGN_MEMBERSHIP,
            user_id,
            post.jurisdiction_ocdid,
            Change(
                entity_type=EntityType.MEMBERSHIP,
                entity_id=membership_id,
                subject=await _person_name(cur, person_id),
                # The seat, which an assignment is read as much by as by who took it.
                detail=label or post.label,
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
