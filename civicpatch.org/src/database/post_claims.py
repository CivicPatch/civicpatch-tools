"""What people claim about a post: its label, headcount and tracked state, and its deletion into
another. No column holds these; they are read back from claims."""

from core.membership_label import post_label
from core.projection.canonical_ids import SAME_AS
from database import claims
from schemas.claims import DefaultNote, Claim, ClaimKind, EntityType, Source

# The fields a human owns, and what a post reads as until somebody claims otherwise. Claims
# only: no column holds them, so deleting a post row loses nothing.
HUMAN_FIELD_DEFAULTS = {"meta_headcount": 1, "meta_is_tracked": True}
HUMAN_FIELDS = tuple(HUMAN_FIELD_DEFAULTS)

# Not a column — 148 dropped `posts.label` in favor of composing it from role and division on
# read. A human can still override that guess ("Position 8" instead of the bare role), the same
# way `memberships.label` overrides its own derivation: as a claim, read back here.
POST_LABEL_FIELD = "label"


def with_label(post: dict, asserted_label: str | None = None) -> dict:
    role_label = post.pop("role_label", None) or post["role_id"]
    return {
        **post,
        "label": post_label(role_label, post["division_ocdid"], asserted_label),
    }


def _accepted(by_field: dict, field: str):
    accepted = by_field.get(field, {}).get(ClaimKind.ACCEPT) or []
    return accepted[0] if accepted else None


def with_claims(post: dict, by_field: dict) -> dict:
    """A posts row with what its claims say: the human fields, else their defaults, and the
    label. `by_field` is one post's entry from `claims.claimed_values`."""
    human_fields = {}
    for field, default in HUMAN_FIELD_DEFAULTS.items():
        claimed = _accepted(by_field, field)
        human_fields[field] = default if claimed is None else claimed
    return with_label({**post, **human_fields}, _accepted(by_field, POST_LABEL_FIELD))


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
        if field in HUMAN_FIELDS and value is not None
    ]


async def accept_fields(
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



async def get_deletion_claim_ids(cur, post_id: str) -> list[str]:
    """The live `same_as` claims that deleted this post into another."""
    await cur.execute(
        """
        SELECT id::text FROM claims
        WHERE entity_type = %s AND entity_id = %s AND field_path = %s AND claim_is_live(id)
        """,
        (EntityType.POST.value, post_id, SAME_AS),
    )
    return [row[0] for row in await cur.fetchall()]


async def undo_deletion(cur, post_id: str, user_id: str, changeset_id: str) -> bool:
    """A post's id is derived from its key, so re-adding a post deleted into another gets the old
    id back, and with it the old `same_as` that would merge it away again. Re-adding undoes that."""
    deletions = await get_deletion_claim_ids(cur, post_id)
    await claims.withdraw_facts(cur, EntityType.CLAIM, deletions, user_id, changeset_id)
    return bool(deletions)
