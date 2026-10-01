from core.membership_label import post_label
from shared.schemas import Post
from core.post_grouping import group_by_organization
from core.projection.facts import PostKey
from database import claims, divisions, organizations
from database.activity import record_change
from database.changesets import create_roster_edit_changeset
from shared.utils.id_utils import make_id
from database.database import get_pool
from schemas.claims import (
    DefaultNote,
    Claim,
    ClaimKind,
    EntityType,
    Source,
)
from schemas.activity import Change, FieldChange
from shared.utils.statuses import ActivityType


class PostHasMembers(Exception):
    """Somebody holds, or once held, this post. Refused rather than cascaded — a membership is
    a person's history, and re-pointing them is the only way past it."""

    def __init__(self, holders: int):
        super().__init__(holders)
        self.holders = holders


class UnknownOrganization(Exception):
    """No organization with this id on this jurisdiction."""


# The fields a human owns, and what a post reads as until somebody claims otherwise. Claims
# only: no column holds them, so deleting a post row loses nothing.
_HUMAN_FIELD_DEFAULTS = {"meta_headcount": 1, "meta_is_tracked": True}
_HUMAN_FIELDS = tuple(_HUMAN_FIELD_DEFAULTS)

# Not a column — 148 dropped `posts.label` in favor of composing it from role and division on
# read. A human can still override that guess ("Position 8" instead of the bare role), the same
# way `memberships.label` overrides its own derivation: as a claim, read back here.
POST_LABEL_FIELD = "label"


def _with_label(post: dict, asserted_label: str | None = None) -> dict:
    role_label = post.pop("role_label", None) or post["role_id"]
    return {
        **post,
        "label": post_label(role_label, post["division_ocdid"], asserted_label),
    }


def _accepted(by_field: dict, field: str):
    accepted = by_field.get(field, {}).get(ClaimKind.ACCEPT) or []
    return accepted[0] if accepted else None


def _with_claims(post: dict, by_field: dict) -> dict:
    """A posts row with what its claims say: the human fields, else their defaults, and the
    label. `by_field` is one post's entry from `claims.claimed_values`."""
    human_fields = {}
    for field, default in _HUMAN_FIELD_DEFAULTS.items():
        claimed = _accepted(by_field, field)
        human_fields[field] = default if claimed is None else claimed
    return _with_label({**post, **human_fields}, _accepted(by_field, POST_LABEL_FIELD))


async def claimed_labels(cur, post_ids: list[str]) -> dict[str, str]:
    """The name a human gave each post, where one did."""
    claimed = await claims.claimed_values(cur, EntityType.POST, post_ids)
    return {
        post_id: accepted[0]
        for post_id, by_field in claimed.items()
        for accepted in [by_field.get(POST_LABEL_FIELD, {}).get(ClaimKind.ACCEPT) or []]
        if accepted
    }


async def claimed_labels_by_key(
    cur, jurisdiction_ocdid: str
) -> dict[tuple[str, str, str], str]:
    """The name a human gave each post in this jurisdiction, keyed by the post's identity.

    By key rather than by id because the fold names a post `uuid5` over that key while the
    stored row's id is random, so the two sides cannot be joined on an id. Through
    `claimed_labels` rather than its own join: clearing a name writes a withdraw, and that
    is the function that knows it.
    """
    await cur.execute(
        """
        SELECT id::text, organization_id::text, role_id, division_ocdid
        FROM posts WHERE jurisdiction_ocdid = %s
        """,
        (jurisdiction_ocdid,),
    )
    rows = await cur.fetchall()
    if not rows:
        return {}
    labels = await claimed_labels(cur, [row[0] for row in rows])
    return {
        (organization_id, role_id, division_ocdid): labels[post_id]
        for post_id, organization_id, role_id, division_ocdid in rows
        if post_id in labels
    }


async def set_post_label(
    cur, post_id: str, label: str, user_id: str, changeset_id: str
) -> None:
    """Name this post. No column to write — this is the whole effect, unlike
    `update_human_fields`'s pair."""
    await claims.upsert(
        cur,
        Claim(
            entity_type=EntityType.POST,
            entity_id=post_id,
            field_path=POST_LABEL_FIELD,
            kind=ClaimKind.ACCEPT,
            value=label,
            sources=[Source(note=DefaultNote.LABEL_SET)],
            changeset_id=changeset_id,
        ),
        user_id,
    )


def _fields_to_accept(values: dict) -> list[tuple[str, object]]:
    """Which of a post's human fields have a value to accept. `value` is NOT NULL, so a field
    nobody answered is left out rather than stored as null."""
    return [
        (field, value)
        for field, value in values.items()
        if field in _HUMAN_FIELDS and value is not None
    ]


async def _accept_fields(
    cur,
    post_id: str,
    values: dict,
    user_id: str,
    changeset_id: str,
) -> None:
    """Accept this post's human fields on somebody's behalf — what makes a hand-made post
    verified. A no-op edit claims nothing new: `upsert_all` skips a value already the current
    answer, so re-saving does not insert a row. Only for a person's act: the derivation's path
    claims nothing, so its posts stay unverified.
    """
    await claims.upsert_all(
        cur,
        [
            Claim(
                entity_type=EntityType.POST,
                entity_id=post_id,
                field_path=field,
                kind=ClaimKind.ACCEPT,
                value=value,
                sources=[Source(note=DefaultNote.EDITED)],
                changeset_id=changeset_id,
            )
            for field, value in _fields_to_accept(values)
        ],
        user_id,
    )


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


async def find_or_create(
    cur,
    jurisdiction_ocdid: str,
    organization_id: str,
    role_id: str,
    division_ocdid: str,
) -> str:
    """Make sure this post exists. Returns its id, minted or matched.

    The scrape's way in, where `create_if_absent` is a person's: a match is not an error to
    report, so the lookup below is the normal path, not a fallback.
    """
    minted = await create_if_absent(
        cur, jurisdiction_ocdid, organization_id, role_id, division_ocdid
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



async def delete_if_unheld(cur, post_id: str) -> bool:
    """Remove a post nobody has ever held. Returns whether it went.

    A post with memberships is history, closed ones included, and stays. The FK would refuse
    anyway; this makes it a 409 rather than a 500.

    Nothing else refuses: whoever vouched for a post and now wants it gone is the same person.
    Its claims go with it, since `claims` has no foreign key to orphan them by.
    """
    await cur.execute(
        """
        DELETE FROM claims
        WHERE entity_type = 'post' AND entity_id::text = %s
          AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.post_id::text = %s)
        """,
        (post_id, post_id),
    )
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


async def get_many(cur, post_ids: list[str]) -> dict[str, Post]:
    """Posts by id. An id with no post is absent rather than None."""
    if not post_ids:
        return {}
    await cur.execute(
        """
        SELECT posts.id::text, posts.jurisdiction_ocdid, posts.organization_id::text,
               posts.role_id, posts.division_ocdid,
               roles.label AS role_label
        FROM posts LEFT JOIN roles ON roles.id = posts.role_id
        WHERE posts.id::text = ANY(%s)
        """,
        (post_ids,),
    )
    columns = [column.name for column in cur.description or []]
    rows = [dict(zip(columns, row)) for row in await cur.fetchall()]
    claimed = await claims.claimed_values(cur, EntityType.POST, [row["id"] for row in rows])
    found = [Post(**_with_claims(row, claimed.get(row["id"], {}))) for row in rows]
    return {post.id: post for post in found}


async def get(cur, post_id: str) -> Post | None:
    """One post by id, or None. `assign` takes the organization from here, never from the
    caller, so a request cannot name a mismatched pair."""
    return (await get_many(cur, [post_id])).get(post_id)


# Nobody holds a post here yet, so every one of them is new: a reporting rule, not a fact about
# a post. Unaliased `posts`, spliced into several queries, per CLAUDE.md.
JURISDICTIONS_FIRST_SCRAPE = """NOT EXISTS (
    SELECT 1 FROM memberships
    JOIN posts held ON held.id = memberships.post_id
    WHERE held.jurisdiction_ocdid = posts.jurisdiction_ocdid
)"""


# Members mean a publish accepted this post; a claim on `_HUMAN_FIELDS` means a human did, which
# reaches posts no publish can — a vacant post is real, and a superseded request can never be
# published. Naming a post is not vouching for it, so a `label` claim does not count.
#
# Not as-of filtered: winding the clock back does not un-vouch a post. The field list is
# `_HUMAN_FIELDS`, spelled out because a LiteralString cannot be joined, and pinned to it by
# `test_the_verified_arm_names_the_human_fields`.
POST_IS_VERIFIED = """(
    EXISTS (SELECT 1 FROM memberships WHERE memberships.post_id = posts.id)
    OR EXISTS (
        SELECT 1 FROM claims
        WHERE claims.entity_type = 'post' AND claims.entity_id = posts.id
          AND claims.field_path IN ('meta_headcount', 'meta_is_tracked')
    )
)"""


async def identities_by_id(cur, post_ids: list[str]) -> dict[str, dict]:
    """The `(organization_id, role_id, division_ocdid)` of each named post — its identity, and
    all the derivation needs from a post a human picked.

    Batched: a roster is read at once, and one query per picked person would put the number of
    round trips in the reviewer's hands.
    """
    if not post_ids:
        return {}
    await cur.execute(
        """
        SELECT id::text, organization_id::text, role_id, division_ocdid
        FROM posts WHERE id::text = ANY(%s)
        """,
        (post_ids,),
    )
    columns = [column.name for column in cur.description or []]
    return {row[0]: dict(zip(columns, row)) for row in await cur.fetchall()}


async def list_for_jurisdiction(cur, jurisdiction_ocdid: str) -> list[dict]:
    by_jurisdiction = await list_for_jurisdictions(cur, [jurisdiction_ocdid])
    return by_jurisdiction.get(jurisdiction_ocdid, [])


async def list_for_jurisdictions(cur, jurisdiction_ocdids: list[str]) -> dict[str, list[dict]]:
    """Every post in each jurisdiction.

    Undated on purpose. A post is not a temporal fact — one minted last week still belongs in
    a June answer — and who holds it at a given moment is the memberships read, which windows
    on `opened_at` and `closed_at`. Vouching is not dated either: winding the clock back
    does not un-vouch a post.
    """
    await cur.execute(
        f"""
        -- `meta_is_verified` is one of the fields no civic standard defines; the other two,
        -- `meta_headcount` and `meta_is_tracked`, come from claims after this read.
        SELECT posts.id::text, posts.jurisdiction_ocdid, posts.organization_id::text,
               posts.role_id, posts.division_ocdid,
               {POST_IS_VERIFIED} AS meta_is_verified,
               roles.label AS role_label
        FROM posts LEFT JOIN roles ON roles.id = posts.role_id
        WHERE posts.jurisdiction_ocdid = ANY(%(jurisdiction_ocdids)s)
        ORDER BY posts.role_id, posts.division_ocdid
        """,
        {"jurisdiction_ocdids": jurisdiction_ocdids},
    )
    columns = [column.name for column in cur.description or []]
    rows = [dict(zip(columns, row)) for row in await cur.fetchall()]
    claimed = await claims.claimed_values(cur, EntityType.POST, [row["id"] for row in rows])
    by_jurisdiction: dict[str, list[dict]] = {}
    for row in rows:
        by_jurisdiction.setdefault(row["jurisdiction_ocdid"], []).append(
            _with_claims(row, claimed.get(row["id"], {}))
        )
    return by_jurisdiction


async def list_page_for_state(
    state: str, limit: int, offset: int
) -> tuple[int, list[dict]]:
    """One page of every post in a state, and the total behind it.

    Same projection as `list_for_jurisdiction`, plus the jurisdiction each belongs to — a
    state-wide read has to say which town a seat is in.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT COUNT(*) OVER() AS total,
                   posts.jurisdiction_ocdid,
                   posts.id::text, posts.organization_id::text, posts.role_id,
                   posts.division_ocdid,
                   {POST_IS_VERIFIED} AS meta_is_verified,
                   roles.label AS role_label
            FROM posts LEFT JOIN roles ON roles.id = posts.role_id
            WHERE posts.jurisdiction_ocdid LIKE %(prefix)s
            ORDER BY posts.jurisdiction_ocdid, posts.role_id, posts.division_ocdid
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {
                "prefix": f"ocd-jurisdiction/country:us/state:{state.lower()}%",
                "limit": limit,
                "offset": offset,
            },
        )
        rows = await cur.fetchall()
        columns = [column.name for column in cur.description or []]
        if not rows:
            return 0, []
        dict_rows = [{k: v for k, v in zip(columns, row) if k != "total"} for row in rows]
        claimed = await claims.claimed_values(
            cur, EntityType.POST, [row["id"] for row in dict_rows]
        )
    total = rows[0][0]
    return total, [_with_claims(row, claimed.get(row["id"], {})) for row in dict_rows]


async def ids_by_identity(
    cur, organization_ids: list[str]
) -> dict[tuple[str, str, str], str]:
    """`(organization, role_id, division_ocdid) -> post id`. Reverse of `identities_by_id`, so
    `propose` can stay pure and unaware of ids.

    Keyed on the organization because that is what `posts_identity_uq` is keyed on. Keyed on the
    jurisdiction it was unambiguous only while a jurisdiction had one body: two bodies with the
    same role and division would collapse onto one key and the dict would keep whichever came
    last.
    """
    if not organization_ids:
        return {}
    await cur.execute(
        """
        SELECT organization_id::text, role_id, division_ocdid, id::text
        FROM posts WHERE organization_id::text = ANY(%s)
        """,
        (organization_ids,),
    )
    return {(row[0], row[1], row[2]): row[3] for row in await cur.fetchall()}


async def unverified_by_jurisdiction(
    cur, jurisdiction_ocdids: list[str]
) -> dict[str, list[dict]]:
    """Posts nobody has vouched for, grouped by jurisdiction.

    A scrape mints a post at ingest; a membership only lands at publish. So an unverified post
    is an office some scrape claimed exists and no human has answered for — and it stays that
    way after the scrape that minted it is superseded, which is why it hangs off the
    jurisdiction rather than off a request. (Keying it on "created by *this* request" would
    lose exactly that: a seat minted by a superseded scrape would go unmentioned forever.)

    Nothing is returned for a jurisdiction that has never been published — see the query.
    """
    if not jurisdiction_ocdids:
        return {}
    await cur.execute(
        f"""
        SELECT posts.jurisdiction_ocdid, posts.id::text, posts.role_id,
               posts.division_ocdid, roles.label AS role_label
        FROM posts
        JOIN roles ON roles.id = posts.role_id
        WHERE posts.jurisdiction_ocdid = ANY(%s) AND NOT {POST_IS_VERIFIED}
          -- Silent on the jurisdiction's first scrape — see the constant.
          AND NOT {JURISDICTIONS_FIRST_SCRAPE}
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
    by_jurisdiction = await list_by_organization_for_jurisdictions([jurisdiction_ocdid])
    return by_jurisdiction[jurisdiction_ocdid]


async def list_by_organization_for_jurisdictions(
    jurisdiction_ocdids: list[str],
) -> dict[str, list[dict]]:
    """`list_by_organization` for many jurisdictions: two queries, whatever the count."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_rows = await organizations.list_for_jurisdictions(cur, jurisdiction_ocdids)
        post_rows = await list_for_jurisdictions(cur, jurisdiction_ocdids)
    return {
        jurisdiction_ocdid: group_by_organization(
            organization_rows.get(jurisdiction_ocdid, []),
            post_rows.get(jurisdiction_ocdid, []),
        )
        for jurisdiction_ocdid in jurisdiction_ocdids
    }


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
            await _accept_fields(
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
                ),
                changeset_id=changeset_id,
            )
        return post_id


async def update(
    post_id: str,
    headcount: int,
    is_tracked: bool,
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
        await _accept_fields(
            cur,
            post_id,
            {"meta_headcount": headcount, "meta_is_tracked": is_tracked},
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
                        ("meta_is_tracked", before.meta_is_tracked, is_tracked),
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


async def ids_in_organizations(
    cur, post_ids: list[str], organization_ids: list[str]
) -> set[str]:
    """Which of these posts belong to those bodies.

    A person can hold one post per organization, so a reviewer's accepted posts may span several:
    this is what picks out the ones the review in front of them is about.
    """
    if not post_ids or not organization_ids:
        return set()
    await cur.execute(
        "SELECT id::text FROM posts WHERE organization_id::text = ANY(%s) AND id::text = ANY(%s)",
        (organization_ids, post_ids),
    )
    return {row[0] for row in await cur.fetchall()}
