"""What each post is called: what its organization calls the role, else the role's own label. The
page's wording stays with each person, in their membership's sources. Pure."""

from collections.abc import Mapping

from shared.utils.taxonomy import UNMATCHED_ROLE_LABEL, Taxonomy

from core.projection.facts import PostKey


def post_role_label(
    post: PostKey, organization_labels: Mapping[str, Mapping[str, str]], taxonomy: Taxonomy
) -> str:
    """`organization_labels` is each organization's `extras_role_labels`, by its id. The `unmatched`
    placeholder is the one role no config file holds."""
    return (
        organization_labels.get(post.organization_id, {}).get(post.role_id)
        or taxonomy.role_labels.get(post.role_id)
        or UNMATCHED_ROLE_LABEL
    )
