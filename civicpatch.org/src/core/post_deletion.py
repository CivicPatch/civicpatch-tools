"""What deleting a post into another one may do, and the fact it files. Pure."""

from shared.schemas import Post

from core.projection.canonical_ids import SAME_AS
from schemas.claims import Claim, ClaimKind, DefaultNote, EntityType, Source


def with_holder_names(organizations: list[dict], holder_names: dict[str, list[str]]) -> list[dict]:
    """Each post with who holds or held it: a held post cannot be deleted outright."""
    return [
        {
            **organization,
            "posts": [
                {**post, "holder_names": holder_names.get(post["id"], [])}
                for post in organization["posts"]
            ],
        }
        for organization in organizations
    ]


def merge_refusal(post: Post, into: Post) -> str | None:
    """Why `into` cannot take this post's memberships, or None if it can. The fold re-reads the
    post's records by organization alone, so only the same office elsewhere can take them."""
    if post.id == into.id:
        return "A post cannot be deleted into itself."
    if post.jurisdiction_ocdid != into.jurisdiction_ocdid:
        return "The post to move to is in another jurisdiction."
    if post.organization_id == into.organization_id:
        return "The post to move to is in the same organization."
    if (post.role_id, post.division_ocdid) != (into.role_id, into.division_ocdid):
        return "The post to move to must have the same role and division."
    return None


def claim_post_same_as(post_id: str, into_post_id: str, changeset_id: str) -> Claim:
    return Claim(
        entity_type=EntityType.POST,
        entity_id=post_id,
        field_path=SAME_AS,
        kind=ClaimKind.ACCEPT,
        value=into_post_id,
        sources=[Source(note=DefaultNote.EDITED)],
        changeset_id=changeset_id,
    )
