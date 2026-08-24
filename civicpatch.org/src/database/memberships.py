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

from datetime import date, datetime, timezone

from database import assertions, posts
from database.change_logs import record_change
from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType
from schemas.change_logs import MembershipChangePayload
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
    person_id: str,
    post_id: str,
    organization_id: str,
    last_seen_at,
    designations: list[str] | None = None,
    unmatched_text: list[str] | None = None,
    source_labels: list[str] | None = None,
    start_date=None,
    end_date=None,
    role_ids: list[str] | None = None,
    label: str | None = None,
) -> str:
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
            last_seen_at = GREATEST(memberships.last_seen_at, EXCLUDED.last_seen_at),
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
            designations or [],
            unmatched_text or [],
            source_labels or [],
            start_date,
            end_date,
            last_seen_at,
            last_seen_at,
            label,
        ),
    )
    membership_id = (await cur.fetchone())[0]
    await _set_membership_roles(cur, membership_id, role_ids or [])
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
    """Memberships with the post they sit on and who holds it — the person-axis read.

    Ordered by person, because that is the axis: the post-axis read already groups the other
    way. `person_name` is joined in for the same reason the change-log payloads carry it —
    an id does not render.

    `as_of` selects on the membership's own interval — open at `first_seen_at`, closed at
    `closed_at` — which is the honest "did they hold it then". None is now, which is
    `closed_at IS NULL`. The posts read is undated: a post is stable, and every one of them
    belongs in the answer whatever date is asked about.

    `source_labels` rides along with `designations` and `unmatched_text` because together with
    the post's role and division they are the whole parse: what the source said, and every
    piece the parser turned it into. That is the answer to "why is this person in this post",
    and it is not reconstructable client-side without re-running the parser.
    """
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
               p.role_id, p.division_ocdid, p.label AS post_label
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        JOIN people pe ON pe.id = m.person_id
        WHERE p.jurisdiction_ocdid = %(jurisdiction_ocdid)s
          AND m.first_seen_at < COALESCE(%(as_of)s::date + 1, now())
          AND (m.closed_at IS NULL OR m.closed_at >= COALESCE(%(as_of)s::date + 1, now()))
        ORDER BY pe.name, p.role_id
        """,
        {"jurisdiction_ocdid": jurisdiction_ocdid, "as_of": as_of},
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def list_by_person(
    jurisdiction_ocdid: str, as_of: date | None = None
) -> list[dict]:
    """The roster by person rather than by post. `as_of` is None for now."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await list_for_jurisdiction(cur, jurisdiction_ocdid, as_of)


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
               p.role_id, p.division_ocdid, p._is_tracked AS is_tracked
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
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


async def update_label(cur, membership_id: str, label: str | None) -> bool:
    """Name this person's post, or clear it back to the derived guess.

    The only human-owned field on a membership, hence the one write outside `upsert`.
    """
    await cur.execute(
        "UPDATE memberships SET label = %s WHERE id::text = %s",
        (label, membership_id),
    )
    return cur.rowcount > 0


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


async def _assert_label(
    cur, membership_id: str, label: str | None, user_id: str
) -> None:
    """Record that a human set this label, so the next scrape leaves it alone.

    Clearing withdraws instead of storing a blank. **This changed with 137**: it used to
    retract, handing the name back to the derivation. It now means the label is empty, and
    stays empty, because a withdrawal and an assertion of nothing are the same row once `value`
    is NOT NULL — and of the two readings, "the human wanted it blank" is the one their action
    actually expressed.
    """
    if label is None:
        await assertions.withdraw(cur, EntityType.MEMBERSHIP, membership_id, LABEL_FIELD)
        return
    await assertions.insert(
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


async def assign(
    person_id: str, post_id: str, label: str | None, user_id: str | None = None
) -> dict:
    """Assign this person, moving them off any other post in the same body.

    A *transition*, always: a different post closes the old membership and opens a new one, so
    "who held that post in June" still answers.

    Returns `{"membership_id", "moved_from"}` so the caller can say which happened.

    Re-assigning to the post they already hold only sets the label — going through `upsert`
    would blank `designations` and `unmatched_text` until the next scrape re-derives them.
    """
    last_seen_at = datetime.now(timezone.utc)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        post = await posts.get(cur, post_id)
        if post is None:
            raise UnknownPost(post_id)

        organization_id = post["organization_id"]
        current = await open_for_person(cur, person_id, organization_id)

        if current and current["post_id"] == post_id:
            await update_label(cur, current["id"], label)
            if user_id:
                await _assert_label(cur, current["id"], label, user_id)
            result = {"membership_id": current["id"], "moved_from": None}
        else:
            membership_id = await upsert(
                cur, person_id, post_id, organization_id, last_seen_at
            )
            if label is not None:
                await update_label(cur, membership_id, label)
                if user_id:
                    await _assert_label(cur, membership_id, label, user_id)
            result = {
                "membership_id": membership_id,
                "moved_from": current["post_id"] if current else None,
            }

        await record_change(
            cur,
            ChangeLogType.ASSIGN_MEMBERSHIP,
            user_id,
            post["jurisdiction_ocdid"],
            MembershipChangePayload(
                membership_id=result["membership_id"],
                person_id=person_id,
                person_name=await _person_name(cur, person_id),
                post_id=post_id,
                role_id=post["role_id"],
                label=label or post["label"],
                moved_from=result["moved_from"],
            ),
        )
        return result
