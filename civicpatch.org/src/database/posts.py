"""Database queries for `posts` — a seat-type within a body.

Identity is the triple `(organization_id, role_id, division_ocdid)`. No free text is in the
key, so renaming a post cannot make the next scrape miss it.

Derivation writes are mint-only: matching a post writes nothing. That is the whole of what
keeps `label` and `headcount` human-owned — there is no update path to lose them through.

Cursor-taking functions compose inside the publish transaction; the connection-owning ones at
the bottom serve the roster screen, and reach `label` and `headcount` where nothing else does.
"""

from datetime import date

from core.post_grouping import group_by_organization, mark_verified
from database import divisions, organizations
from database.change_logs import record_change
from database.database import get_pool
from schemas.change_logs import FieldChange, PostChangePayload
from shared.utils.statuses import ChangeLogType


async def create_if_absent(
    cur,
    jurisdiction_ocdid: str,
    organization_id: str,
    role_id: str,
    division_ocdid: str,
    label: str | None = None,
    headcount: int = 1,
) -> str | None:
    """Insert a post, or None if the triple is taken. The only INSERT in this module.

    `label` and `headcount` land only here, on mint — a later scrape must not overwrite what
    somebody typed, which is why neither is ever recomputed.
    """
    await cur.execute(
        """
        INSERT INTO posts
            (jurisdiction_ocdid, organization_id, role_id, division_ocdid, label, headcount)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (organization_id, role_id, division_ocdid) DO NOTHING
        RETURNING id::text
        """,
        (
            jurisdiction_ocdid,
            organization_id,
            role_id,
            division_ocdid,
            label,
            headcount,
        ),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def find_or_create(
    cur,
    jurisdiction_ocdid: str,
    organization_id: str,
    role_id: str,
    division_ocdid: str,
    headcount: int = 1,
) -> str:
    """Make sure this post exists. Returns its id, minted or matched.

    The scrape's way in, where `create_if_absent` is a person's: a match is not an error to
    report, so the lookup below is the normal path, not a fallback. No `label` — only a person
    names a seat.
    """
    minted = await create_if_absent(
        cur,
        jurisdiction_ocdid,
        organization_id,
        role_id,
        division_ocdid,
        headcount=headcount,
    )
    if minted:
        return minted

    await cur.execute(
        """
        SELECT id::text FROM posts
        WHERE organization_id = %s AND role_id = %s AND division_ocdid = %s
        """,
        (organization_id, role_id, division_ocdid),
    )
    return (await cur.fetchone())[0]


async def update_human_fields(
    cur, post_id: str, label: str | None, headcount: int
) -> bool:
    """Set the two columns a person owns. The only update path to a post."""
    await cur.execute(
        "UPDATE posts SET label = %s, headcount = %s WHERE id::text = %s",
        (label, headcount, post_id),
    )
    return cur.rowcount > 0


async def delete_if_unheld(cur, post_id: str) -> bool:
    """Remove a post nobody has ever held. Returns whether it went.

    A post with memberships is history, closed ones included, and stays. The FK would refuse
    anyway; this makes it a 409 rather than a 500.
    """
    await cur.execute(
        """
        DELETE FROM posts
        WHERE id::text = %s
          AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.post_id = posts.id)
        """,
        (post_id,),
    )
    return cur.rowcount > 0


async def get(cur, post_id: str) -> dict | None:
    """One post by id, or None. `assign` takes the organization from here, never from the
    caller, so a request cannot name a mismatched pair."""
    await cur.execute(
        """
        SELECT id::text, jurisdiction_ocdid, organization_id::text, role_id, division_ocdid,
               label, headcount
        FROM posts WHERE id::text = %s
        """,
        (post_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return dict(zip([c.name for c in cur.description or []], row))


async def list_for_jurisdiction(
    cur, jurisdiction_ocdid: str, as_of: date | None = None
) -> list[dict]:
    """Every post in a jurisdiction with the people holding it. `as_of` is None for now.

    A date means the *end* of that day, so `as_of=today` agrees with the default; midnight
    would drop everything observed this morning.

    Transaction time — "who did the source list then", not "who held office". Posts are not
    dated, so one minted last week still appears in a June query, with no holders.
    """
    await cur.execute(
        """
        SELECT p.id::text, p.organization_id::text, p.role_id, p.division_ocdid,
               p.label, p.headcount,
               -- Not as-of filtered: winding the clock back does not un-vouch a seat.
               count(m.id) > 0 AS verified,
               count(m.id) FILTER (
                   WHERE m.first_seen_at < COALESCE(%(as_of)s::date + 1, now())
                     AND (m.closed_at IS NULL
                          OR m.closed_at >= COALESCE(%(as_of)s::date + 1, now()))
               ) AS holders,
               -- Gated on its own timestamp: an April read must not report a May sighting.
               -- Errs toward NULL, since only the newest observation per row is kept.
               max(m.last_seen_at) FILTER (
                   WHERE m.last_seen_at < COALESCE(%(as_of)s::date + 1, now())
               ) AS last_seen_at
        FROM posts p
        LEFT JOIN memberships m ON m.post_id = p.id
        WHERE p.jurisdiction_ocdid = %(jurisdiction_ocdid)s
        GROUP BY p.id
        ORDER BY p.role_id, p.division_ocdid
        """,
        {"as_of": as_of, "jurisdiction_ocdid": jurisdiction_ocdid},
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def unseen_since(cur, jurisdiction_ocdid: str, cutoff) -> list[dict]:
    """Posts a person once endorsed that no scrape has produced since `cutoff`.

    The HAVING drops never-endorsed posts: nothing was seen in them, so they cannot have
    stopped being seen. A seat nobody has confirmed is unconfirmed, not absent.
    """
    await cur.execute(
        """
        SELECT p.id::text, p.role_id, p.division_ocdid, p.label,
               max(m.last_seen_at) AS last_seen_at
        FROM posts p
        LEFT JOIN memberships m ON m.post_id = p.id
        WHERE p.jurisdiction_ocdid = %s
        GROUP BY p.id
        HAVING max(m.last_seen_at) < %s
        ORDER BY max(m.last_seen_at)
        """,
        (jurisdiction_ocdid, cutoff),
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def list_by_organization(
    jurisdiction_ocdid: str, as_of: date | None = None
) -> list[dict]:
    """Every body in a jurisdiction with its posts. `as_of` selects holders; None is now."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_rows = await organizations.list_for_jurisdiction(
            cur, jurisdiction_ocdid
        )
        post_rows = await list_for_jurisdiction(cur, jurisdiction_ocdid, as_of)
    return group_by_organization(organization_rows, mark_verified(post_rows))


async def create(
    jurisdiction_ocdid: str,
    role_id: str,
    division_ocdid: str,
    label: str | None,
    headcount: int,
    user_id: str | None = None,
) -> str | None:
    """A person asserting a seat exists. Returns its id, or None if it already did.

    Organization and division are found-or-created on the way — a division exists because a
    post needs it, never on its own.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, jurisdiction_ocdid)
        await divisions.find_or_create(cur, division_ocdid, jurisdiction_ocdid)
        post_id = await create_if_absent(
            cur,
            jurisdiction_ocdid,
            organization_id,
            role_id,
            division_ocdid,
            label=label,
            headcount=headcount,
        )
        # Nothing to log when the triple was taken: no seat was created.
        if post_id:
            await record_change(
                cur,
                ChangeLogType.ADD_POST,
                user_id,
                jurisdiction_ocdid,
                PostChangePayload(
                    post_id=post_id,
                    role_id=role_id,
                    division_ocdid=division_ocdid,
                    label=label,
                ),
            )
        return post_id


async def update(
    post_id: str, label: str | None, headcount: int, user_id: str | None = None
) -> bool:
    """Set the two human-owned fields, logging what actually moved.

    Read before write so the log can carry before/after. A no-op edit still logs — somebody
    looked at this seat and confirmed it, which is worth as much as a change.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        before = await get(cur, post_id)
        if before is None:
            return False

        await update_human_fields(cur, post_id, label, headcount)
        await record_change(
            cur,
            ChangeLogType.EDIT_POST,
            user_id,
            before["jurisdiction_ocdid"],
            PostChangePayload(
                post_id=post_id,
                role_id=before["role_id"],
                division_ocdid=before["division_ocdid"],
                label=label,
                fields=[
                    FieldChange(field=field, before=before[field], after=after)
                    for field, after in (("label", label), ("headcount", headcount))
                    if before[field] != after
                ],
            ),
        )
        return True


async def delete(post_id: str, user_id: str | None = None) -> bool:
    """Remove a post nobody has held. False means it has members, or does not exist.

    Read first: once the row is gone there is nothing left to describe it with, and a log
    saying only "a post was deleted" is not worth writing.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        before = await get(cur, post_id)
        if before is None or not await delete_if_unheld(cur, post_id):
            return False

        await record_change(
            cur,
            ChangeLogType.DELETE_POST,
            user_id,
            before["jurisdiction_ocdid"],
            PostChangePayload(
                post_id=post_id,
                role_id=before["role_id"],
                division_ocdid=before["division_ocdid"],
                label=before["label"],
            ),
        )
        return True
