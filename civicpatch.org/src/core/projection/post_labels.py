"""What each post is called: its role as the page wrote it, from the newest membership in it that
names it; else what the organization calls the role; else the role's own label. Pure."""

from collections.abc import Mapping, Sequence

from shared.utils.taxonomy import UNMATCHED_ROLE_LABEL, Taxonomy

from core.projection.facts import PostKey
from core.projection.membership_history import MembershipRow


def post_role_labels(
    history: Sequence[MembershipRow],
    organization_labels: Mapping[str, Mapping[str, str]],
    taxonomy: Taxonomy,
) -> dict[str, str]:
    """By post id. `organization_labels` is each organization's `extras_role_labels`, by its id."""
    newest_first = sorted(history, key=lambda row: (row.closed_at is None, row.opened_at), reverse=True)
    page_texts: dict[str, str] = {}
    for row in newest_first:
        role_text = row.membership.role_text
        if role_text and row.membership.post.post_id not in page_texts:
            page_texts[row.membership.post.post_id] = role_text

    posts = {row.membership.post.post_id: row.membership.post for row in history}
    return {
        post_id: page_texts.get(post_id) or label_without_page(post, organization_labels, taxonomy)
        for post_id, post in posts.items()
    }


def label_without_page(
    post: PostKey, organization_labels: Mapping[str, Mapping[str, str]], taxonomy: Taxonomy
) -> str:
    """A post no page has named: what its organization calls the role, else the role's label. The
    `unmatched` placeholder is the one role no config file holds."""
    return (
        organization_labels.get(post.organization_id, {}).get(post.role_id)
        or taxonomy.role_labels.get(post.role_id)
        or UNMATCHED_ROLE_LABEL
    )
