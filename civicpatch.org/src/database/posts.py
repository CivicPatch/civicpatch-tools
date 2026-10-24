"""Writing posts: minting, editing and deleting the rows."""

from core.projection.facts import PostKey
from database import divisions, organizations
from database.activity import record_change
from database.changesets import create_roster_edit_changeset
from database.database import get_pool
from database.post_claims import accept_fields, set_post_label, undo_deletion
from database.post_listings import get
from schemas.activity import Change, FieldChange
from schemas.claims import EntityType
from shared.utils.id_utils import make_id
from shared.utils.statuses import ActivityType

class PostHasMembers(Exception):
    """Somebody holds, or once held, this post. Refused rather than cascaded — a membership is
    a person's history, and re-pointing them is the only way past it."""

    def __init__(self, holders: int):
        super().__init__(holders)
        self.holders = holders


class UnknownOrganization(Exception):
    """No organization with this id on this jurisdiction."""


async def create_if_absent(
    cur,
    jurisdiction_ocdid: str,
    organization_id: str,
    role_id: str,
    division_ocdid: str,
) -> str | None:
    """Insert a post, or None if the triple is taken. The only INSERT in this module.

    A row is only its key: what a person says about it (headcount, tracked, label) is claims.
    """
    post_id = PostKey(
        organization_id=organization_id, role_id=role_id, division_ocdid=division_ocdid
    ).post_id
    await cur.execute(
        """
        INSERT INTO posts (id, jurisdiction_ocdid, organization_id, role_id, division_ocdid)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (organization_id, role_id, division_ocdid) DO NOTHING
        RETURNING id::text
        """,
        (post_id, jurisdiction_ocdid, organization_id, role_id, division_ocdid),
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def delete_if_unheld(cur, post_id: str) -> bool:
    """Remove a post nobody has ever held. Returns whether it went.

    A post with memberships is history, closed ones included, and stays. The FK would refuse
    anyway; this makes it a 409 rather than a 500.

    Nothing else refuses: whoever vouched for a post and now wants it gone is the same person.
    Its claims stay: facts are append-only (R1), and a claim about a post that is gone is inert.
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


async def _holder_count(cur, post_id: str) -> int:
    await cur.execute(
        "SELECT count(*) FROM memberships WHERE memberships.post_id = %s", (post_id,)
    )
    return (await cur.fetchone())[0]


async def _refuse_if_held(cur, post_id: str) -> None:
    """Say why a post cannot go, before trying to delete it.

    Only holders refuse. A person's *history* blocks a delete; their *opinion* does not —
    somebody who vouched for a post and has since decided it is wrong is the very person
    deleting it, and making them withdraw the vouch first is a step with no way to take it.
    """
    await cur.execute(
        "SELECT count(*) FROM memberships WHERE memberships.post_id = %s", (post_id,)
    )
    if (await cur.fetchone())[0]:
        raise PostHasMembers((await _holder_count(cur, post_id)))


async def create(
    organization_id: str,
    role_id: str,
    division_ocdid: str,
    headcount: int,
    user_id: str,
    label: str | None = None,
) -> str | None:
    """A person asserting a post exists. Returns its id, or None if it already did.

    The jurisdiction is the organization's own — a post always belongs to one of an
    organization's existing bodies, never named separately by the caller. The division is
    found-or-created on the way, since it exists because a post needs it, never on its own.

    `label` overrides the derived guess ("Position 8" instead of the bare role) — claimed,
    like `meta_headcount`, not stored as its own column. Always a person: a scrape mints through
    `create_if_absent` and claims nothing.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        jurisdiction_ocdid = await organizations.jurisdiction_for(cur, organization_id)
        if jurisdiction_ocdid is None:
            raise UnknownOrganization(organization_id)
        await divisions.find_or_create(cur, division_ocdid, jurisdiction_ocdid)
        post_id = await create_if_absent(
            cur, jurisdiction_ocdid, organization_id, role_id, division_ocdid
        )
        # Nothing to log when the triple was taken: no post was created.
        if post_id:
            changeset_id = make_id()
            await create_roster_edit_changeset(cur, changeset_id, jurisdiction_ocdid, user_id)
            undid_deletion = await undo_deletion(cur, post_id, user_id, changeset_id)
            await accept_fields(
                cur, post_id, {"meta_headcount": headcount}, user_id, changeset_id
            )
            if label:
                await set_post_label(cur, post_id, label, user_id, changeset_id)
            minted = await get(cur, post_id)
            await record_change(
                cur,
                ActivityType.ADD_POST,
                user_id,
                jurisdiction_ocdid,
                Change(
                    entity_type=EntityType.POST,
                    entity_id=post_id,
                    subject=(minted.label if minted else None) or role_id,
                    detail="Undid an earlier deletion into another post." if undid_deletion else None,
                ),
                changeset_id=changeset_id,
            )
        return post_id


async def update(
    post_id: str,
    headcount: int,
    user_id: str,
) -> str | None:
    """Set the human-owned fields, logging what actually moved. Returns the jurisdiction, or
    None when there is no such post.

    The jurisdiction rather than a bare bool because the caller has to mirror the change
    outward and cannot ask afterwards — it is already read here for the change log.

    Read before write so the log can carry before/after. A no-op edit still logs — somebody
    looked at this post and confirmed it, which is worth as much as a change. Claims are the
    whole effect.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        before = await get(cur, post_id)
        if before is None:
            return None

        changeset_id = make_id()
        await create_roster_edit_changeset(cur, changeset_id, before.jurisdiction_ocdid, user_id)
        await accept_fields(
            cur,
            post_id,
            {"meta_headcount": headcount},
            user_id,
            changeset_id,
        )
        await record_change(
            cur,
            ActivityType.EDIT_POST,
            user_id,
            before.jurisdiction_ocdid,
            Change(
                entity_type=EntityType.POST,
                entity_id=post_id,
                # Derived, and unchanged by this edit: it names the seat for a reader.
                subject=before.label or before.role_id,
                fields=[
                    FieldChange(field=field, before=was, after=now)
                    for field, was, now in (
                        ("meta_headcount", before.meta_headcount, headcount),
                    )
                    if was != now
                ],
            ),
            changeset_id=changeset_id,
        )
        return before.jurisdiction_ocdid


async def delete(post_id: str, user_id: str | None = None) -> bool:
    """Remove a post nobody has held. False means it does not exist.

    Raises rather than returning False when something holds it, so the caller can say which of
    the two happened — "no such post" and "five people hold this" want different words, and one
    of them tells a reviewer what to do next.

    Read first: once the row is gone there is nothing left to describe it with, and a log
    saying only "a post was deleted" is not worth writing.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await delete_on(cur, post_id, user_id)


async def delete_on(cur, post_id: str, user_id: str | None = None) -> bool:
    """`delete` on the caller's cursor, so a refusal rolls back whatever the caller did first."""
    before = await get(cur, post_id)
    if before is None:
        return False
    await _refuse_if_held(cur, post_id)
    if not await delete_if_unheld(cur, post_id):
        return False

    await record_change(
        cur,
        ActivityType.DELETE_POST,
        user_id,
        before.jurisdiction_ocdid,
        Change(
            entity_type=EntityType.POST,
            entity_id=post_id,
            subject=before.label or before.role_id,
        ),
    )
    return True
