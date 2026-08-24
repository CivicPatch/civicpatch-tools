"""Database queries for `posts` — one office within a body, not who holds it.

Identity is the triple `(organization_id, role_id, division_ocdid)`. No free text is in the
key, so renaming a post cannot make the next scrape miss it.

Derivation writes are mint-only: matching a post writes nothing. That is the whole of what
keeps `label` and `headcount` human-owned — there is no update path to lose them through.

"""

from core.membership_label import derive_label
from core.post_derivation import DerivedPost
from core.post_grouping import group_by_organization
from database import divisions, organizations, roles
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
    is_tracked: bool = True,
) -> str | None:
    """Insert a post, or None if the triple is taken. The only INSERT in this module.

    All of them land only here, on mint — a later scrape must not overwrite what somebody
    typed, which is why none is ever recomputed. An absent `label` is suggested from the role
    and division, so a post is never nameless before somebody gets to it.

    `_headcount` and `_is_tracked` carry their prefix as column names, because no civic
    standard defines either. The Python arguments drop it: a leading underscore means
    something else here.
    """
    if label is None:
        role = await roles.get_role(cur, role_id)
        if role:
            label = derive_label(role.label, division_ocdid, [], [])

    await cur.execute(
        """
        INSERT INTO posts
            (jurisdiction_ocdid, organization_id, role_id, division_ocdid, label, _headcount, _is_tracked)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
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
            is_tracked,
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
    is_tracked: bool = True,
) -> str:
    """Make sure this post exists. Returns its id, minted or matched.

    The scrape's way in, where `create_if_absent` is a person's: a match is not an error to
    report, so the lookup below is the normal path, not a fallback.
    """
    minted = await create_if_absent(
        cur,
        jurisdiction_ocdid,
        organization_id,
        role_id,
        division_ocdid,
        headcount=headcount,
        is_tracked=is_tracked,
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
    cur, post_id: str, label: str | None, headcount: int, is_tracked: bool
) -> bool:
    """Set the columns a person owns. The only update path to a post.

    `is_tracked` is seeded at mint from whether the role was recognised, which is a guess.
    This is where a person corrects it — the clerk their town elects, the attorney it does not.
    """
    await cur.execute(
        "UPDATE posts SET label = %s, _headcount = %s, _is_tracked = %s WHERE id::text = %s",
        (label, headcount, is_tracked, post_id),
    )
    return cur.rowcount > 0


async def delete_if_unheld(cur, post_id: str) -> bool:
    """Remove a post nobody has ever held or vouched for. Returns whether it went.

    A post with memberships is history, closed ones included, and stays. The FK would refuse
    anyway; this makes it a 409 rather than a 500.

    A post with assertions is history too, and nothing refuses that on its behalf — `assertions`
    has no foreign key, so deleting would orphan the rows silently. It would also discard the
    only copy of why someone vouched for it: "phoned the clerk, there really are five trustees"
    exists nowhere else, because it came from outside a publish.
    """
    await cur.execute(
        """
        DELETE FROM posts
        WHERE id::text = %s
          AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.post_id = posts.id)
          AND NOT EXISTS (
              SELECT 1 FROM assertions a
              WHERE a.entity_type = 'post' AND a.entity_id = posts.id
          )
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
               label, _headcount, _is_tracked
        FROM posts WHERE id::text = %s
        """,
        (post_id,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    return dict(zip([c.name for c in cur.description or []], row))


# Two ways a human vouches for a post. Having members means a publish accepted it — true only
# while memberships are written solely at publish, and deriving at ingest breaks that. An
# assertion also reaches posts no publish can: a transient's request was superseded, so the
# guard refuses to publish it.
#
# Not as-of filtered: winding the clock back does not un-vouch a post. Unaliased, so a caller
# cannot be required to spell `posts` any particular way.
POST_IS_VERIFIED = """(
    EXISTS (SELECT 1 FROM memberships WHERE memberships.post_id = posts.id)
    OR EXISTS (
        SELECT 1 FROM assertions
        WHERE assertions.entity_type = 'post' AND assertions.entity_id = posts.id
          AND assertions.field_path IS NULL AND assertions.kind = 'confirm'
    )
)"""


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    """Every post in a jurisdiction.

    Undated on purpose. A post is not a temporal fact — one minted last week still belongs in
    a June answer — and who holds it at a given moment is the memberships read, which windows
    on `first_seen_at` and `closed_at`. Vouching is not dated either: winding the clock back
    does not un-vouch a post.
    """
    await cur.execute(
        f"""
        -- `_*` are the fields no civic standard defines: a consumer dropping them is left
        -- with a conforming Post. Stored ones carry the prefix as their column name; only a
        -- computed one like `_is_verified` needs an alias to get it.
        SELECT posts.id::text, posts.organization_id::text, posts.role_id, posts.division_ocdid,
               posts.label, posts._headcount, posts._is_tracked,
               {POST_IS_VERIFIED} AS _is_verified
        FROM posts
        WHERE posts.jurisdiction_ocdid = %(jurisdiction_ocdid)s
        ORDER BY posts.role_id, posts.division_ocdid
        """,
        {"jurisdiction_ocdid": jurisdiction_ocdid},
    )
    columns = [column.name for column in cur.description or []]
    return [dict(zip(columns, row)) for row in await cur.fetchall()]


async def unverified_by_jurisdiction(
    cur, jurisdiction_ocdids: list[str]
) -> dict[str, list[dict]]:
    """Posts nobody has vouched for, grouped by jurisdiction.

    A scrape mints a post at ingest; a membership only lands at publish. So an unverified post
    is an office some scrape asserted exists and no human has answered for — and it stays that
    way after the scrape that minted it is superseded, which is why it hangs off the
    jurisdiction rather than off a request.
    """
    if not jurisdiction_ocdids:
        return {}
    await cur.execute(
        f"""
        SELECT posts.jurisdiction_ocdid, posts.id::text, posts.role_id,
               posts.division_ocdid, posts.label, roles.label AS role_label
        FROM posts
        JOIN roles ON roles.id = posts.role_id
        WHERE posts.jurisdiction_ocdid = ANY(%s) AND NOT {POST_IS_VERIFIED}
        ORDER BY posts.role_id, posts.division_ocdid
        """,
        (jurisdiction_ocdids,),
    )
    columns = [column.name for column in cur.description or []]
    grouped: dict[str, list[dict]] = {ocdid: [] for ocdid in jurisdiction_ocdids}
    for row in await cur.fetchall():
        post = dict(zip(columns, row))
        grouped[post.pop("jurisdiction_ocdid")].append(post)
    return grouped


async def list_by_organization(jurisdiction_ocdid: str) -> list[dict]:
    """Every body in a jurisdiction with its posts."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_rows = await organizations.list_for_jurisdiction(
            cur, jurisdiction_ocdid
        )
        post_rows = await list_for_jurisdiction(cur, jurisdiction_ocdid)
    return group_by_organization(organization_rows, post_rows)


async def find_or_create_all(
    jurisdiction_ocdid: str, derived: list[DerivedPost]
) -> None:
    """A whole scrape's worth of `find_or_create`, in one transaction.

    No change log, unlike `create` below: no person asserted these.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, jurisdiction_ocdid)
        for post in derived:
            await divisions.find_or_create(cur, post.division_ocdid, jurisdiction_ocdid)
            await find_or_create(
                cur,
                jurisdiction_ocdid,
                organization_id,
                post.role_id,
                post.division_ocdid,
                headcount=post.headcount,
            )
        await conn.commit()


async def create(
    jurisdiction_ocdid: str,
    role_id: str,
    division_ocdid: str,
    label: str | None,
    headcount: int,
    user_id: str | None = None,
) -> str | None:
    """A person asserting a post exists. Returns its id, or None if it already did.

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
        # Nothing to log when the triple was taken: no post was created.
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
    post_id: str,
    label: str | None,
    headcount: int,
    is_tracked: bool,
    user_id: str | None = None,
) -> bool:
    """Set the human-owned fields, logging what actually moved.

    Read before write so the log can carry before/after. A no-op edit still logs — somebody
    looked at this post and confirmed it, which is worth as much as a change.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        before = await get(cur, post_id)
        if before is None:
            return False

        await update_human_fields(cur, post_id, label, headcount, is_tracked)
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
                    for field, after in (
                        ("label", label),
                        ("_headcount", headcount),
                        ("_is_tracked", is_tracked),
                    )
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
