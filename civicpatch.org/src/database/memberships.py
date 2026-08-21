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

from datetime import datetime, timezone

from database import posts
from database.database import get_pool

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
    start_date=None,
    end_date=None,
    role_id: str | None = None,
) -> str:
    """Open this person's membership of this post, or advance it. Returns its id.

    Closing their other open seat first is what makes the insert collide only with the
    same-post case, so "one open per body" holds without the insert testing for it.

    `seen_at` is when the source said this, not when the row was written.

    `role_id` is a title held in a seat some other role defines — `mayor` for a councilmember
    serving as mayor. `designations` tell like seats apart ("Place 2"); `unmatched_text` is
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
            (post_id, organization_id, person_id, designations, unmatched_text, role_id,
             start_date, end_date, first_seen_at, last_seen_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (person_id, organization_id) WHERE closed_at IS NULL
        DO UPDATE SET
            last_seen_at = GREATEST(memberships.last_seen_at, EXCLUDED.last_seen_at),
            designations = EXCLUDED.designations,
            unmatched_text = EXCLUDED.unmatched_text,
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


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    """Open memberships with the post they sit on — the person-axis read."""
    await cur.execute(
        """
        SELECT m.id::text, m.person_id::text, m.post_id::text, m.label,
               m.start_date, m.end_date, m.first_seen_at, m.last_seen_at,
               p.role_id, p.division_ocdid
        FROM memberships m
        JOIN posts p ON p.id = m.post_id
        WHERE p.jurisdiction_ocdid = %s AND m.closed_at IS NULL
        ORDER BY p.role_id, p.division_ocdid
        """,
        (jurisdiction_ocdid,),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def unmatched_text() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT mode() WITHIN GROUP (ORDER BY term) AS text,
                   count(*) AS occurrences,
                   count(DISTINCT p.jurisdiction_ocdid) AS jurisdictions,
                   (array_agg(DISTINCT p.jurisdiction_ocdid
                              ORDER BY p.jurisdiction_ocdid))[1:3] AS examples
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
    """Name this person's seat, or clear it back to the derived guess.

    The only human-owned field on a membership, hence the one write outside `record`.
    """
    await cur.execute(
        "UPDATE memberships SET label = %s WHERE id::text = %s",
        (label, membership_id),
    )
    return cur.rowcount > 0


async def open_for_person(cur, person_id: str, organization_id: str) -> dict | None:
    """This person's current seat in this body. At most one row —
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


async def assign(person_id: str, post_id: str, label: str | None) -> dict:
    """Seat this person, moving them off any other seat in the same body.

    A *transition*, always: a different post closes the old membership and opens a new one, so
    "who held that seat in June" still answers.

    Returns `{"membership_id", "moved_from"}` so the caller can say which happened.

    Re-assigning to the seat they already hold only sets the label — going through `record`
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
            return {"membership_id": current["id"], "moved_from": None}

        membership_id = await record(cur, person_id, post_id, organization_id, seen_at)
        if label is not None:
            await update_label(cur, membership_id, label)

        return {
            "membership_id": membership_id,
            "moved_from": current["post_id"] if current else None,
        }
