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

from database import posts
from database.change_logs import record_change
from database.database import get_pool
from schemas.change_logs import MembershipChangePayload
from shared.utils.statuses import ChangeLogType

TRIAGE_LIMIT = 100


class UnknownPost(Exception):
    """The post id does not exist."""


async def record(
    cur,
    person_id: str,
    post_id: str,
    organization_id: str,
    seen_at,
    designations: list[str] | None = None,
    unmatched_text: list[str] | None = None,
    source_labels: list[str] | None = None,
    start_date=None,
    end_date=None,
    role_id: str | None = None,
) -> str:
    """Open this person's membership of this post, or advance it. Returns its id.

    Closing their other open membership first is what makes the insert collide only with the
    same-post case, so "one open per body" holds without the insert testing for it.

    `seen_at` is when the source said this, not when the row was written.

    `source_labels` is what the source called this post, already split. Written here rather
    than joined back to `source_records` so it cannot disagree with the `unmatched_text`
    derived from it.

    `role_id` is a title held in a post some other role defines — `mayor` for a councilmember
    serving as mayor. `designations` tell like posts apart ("Place 2"); `unmatched_text` is
    what the parser could not classify.

    **`label` is deliberately absent from the conflict update.** Leaving it out of the SET is
    the whole of its protection.
    """
    await cur.execute(
        """
        UPDATE memberships SET closed_at = %s
        WHERE person_id = %s AND organization_id = %s
          AND closed_at IS NULL AND post_id <> %s
        """,
        (seen_at, person_id, organization_id, post_id),
    )

    await cur.execute(
        """
        INSERT INTO memberships
            (post_id, organization_id, person_id, designations, unmatched_text,
             source_labels, role_id, start_date, end_date, first_seen_at, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (person_id, organization_id) WHERE closed_at IS NULL
        DO UPDATE SET
            last_seen_at = GREATEST(memberships.last_seen_at, EXCLUDED.last_seen_at),
            designations = EXCLUDED.designations,
            unmatched_text = EXCLUDED.unmatched_text,
            source_labels = EXCLUDED.source_labels,
            role_id = EXCLUDED.role_id,
            start_date = EXCLUDED.start_date,
            end_date = EXCLUDED.end_date
        RETURNING id::text
        """,
        (
            post_id,
            organization_id,
            person_id,
            designations or [],
            unmatched_text or [],
            source_labels or [],
            role_id,
            start_date,
            end_date,
            seen_at,
            seen_at,
        ),
    )
    return (await cur.fetchone())[0]


async def close_absent(
    cur, jurisdiction_ocdid: str, present_person_ids: list[str], closed_at
) -> int:
    """Close open memberships for anyone the scrape did not name.

    An empty roster closes nobody — that is a failed scrape, not a dissolved council.
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

    `as_of` is the same window `posts.list_for_jurisdiction` uses, so the two axes answer the
    same question about the same moment. None is now, which is `closed_at IS NULL`.

    `source_labels` rides along with `designations` and `unmatched_text` because together with
    the post's role and division they are the whole parse: what the source said, and every
    piece the parser turned it into. That is the answer to "why is this person in this post",
    and it is not reconstructable client-side without re-running the parser.
    """
    await cur.execute(
        """
        SELECT m.id::text, m.person_id::text, m.post_id::text, m.label,
               m.start_date, m.end_date, m.first_seen_at, m.last_seen_at,
               pe.data->>'name' AS person_name,
               m.source_labels, m.designations, m.unmatched_text,
               p.role_id, p.division_ocdid, p.label AS post_label
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        JOIN people pe ON pe.id = m.person_id
        WHERE p.jurisdiction_ocdid = %(jurisdiction_ocdid)s
          AND m.first_seen_at < COALESCE(%(as_of)s::date + 1, now())
          AND (m.closed_at IS NULL OR m.closed_at >= COALESCE(%(as_of)s::date + 1, now()))
        ORDER BY pe.data->>'name', p.role_id
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


async def unmatched_text() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
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
            FROM memberships m
            JOIN posts p ON p.id = m.post_id
            CROSS JOIN LATERAL unnest(m.unmatched_text) AS term
            WHERE m.closed_at IS NULL
            GROUP BY lower(term)
            ORDER BY count(DISTINCT p.jurisdiction_ocdid) DESC, count(*) DESC,
                     lower(term)
            LIMIT %s
            """,
            (TRIAGE_LIMIT,),
        )
        columns = [column.name for column in cur.description or []]
        return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def update_label(cur, membership_id: str, label: str | None) -> bool:
    """Name this person's post, or clear it back to the derived guess.

    The only human-owned field on a membership, hence the one write outside `record`.
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
    await cur.execute("SELECT data->>'name' FROM people WHERE id = %s", (person_id,))
    row = await cur.fetchone()
    return (row[0] if row else None) or person_id


async def assign(
    person_id: str, post_id: str, label: str | None, user_id: str | None = None
) -> dict:
    """Assign this person, moving them off any other post in the same body.

    A *transition*, always: a different post closes the old membership and opens a new one, so
    "who held that post in June" still answers.

    Returns `{"membership_id", "moved_from"}` so the caller can say which happened.

    Re-assigning to the post they already hold only sets the label — going through `record`
    would blank `designations` and `unmatched_text` until the next scrape re-derives them.
    """
    seen_at = datetime.now(timezone.utc)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        post = await posts.get(cur, post_id)
        if post is None:
            raise UnknownPost(post_id)

        organization_id = post["organization_id"]
        current = await open_for_person(cur, person_id, organization_id)

        if current and current["post_id"] == post_id:
            await update_label(cur, current["id"], label)
            result = {"membership_id": current["id"], "moved_from": None}
        else:
            membership_id = await record(
                cur, person_id, post_id, organization_id, seen_at
            )
            if label is not None:
                await update_label(cur, membership_id, label)
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
