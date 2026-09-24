"""What a reviewer is told about a changeset before they open it.

Both sides of the fold, compared: how many people it adds, changes and drops, and the issues
that follow from the posts it fills. Filed apart from the proposal layer it grew up in — the
summary is read off the fold, and outlives that layer's deletion.
"""

from core.post_issues import unverified_post_issues
from core.projection.diff import roster_diff
from core.review_summary import ReviewSummary, fold_card_summary
from database import source_records
from database import changesets as changesets_db
from database import organizations as organizations_db
from database import posts as posts_db
from database.database import get_pool
from database.roles import get_roles
from services.roster import CardFold, card_fold
from shared.schemas import Issue, RoleConfig
from shared.utils.config_utils import get_unique_roles


async def review_summary_for_changeset(changeset_id: str) -> ReviewSummary:
    jurisdiction_ocdid = await changesets_db.get_changeset_jurisdiction(changeset_id)
    if not jurisdiction_ocdid:
        return ReviewSummary()
    fold = await card_fold(changeset_id, jurisdiction_ocdid)
    return await summary_of(changeset_id, jurisdiction_ocdid, fold)


async def summary_of(
    changeset_id: str, jurisdiction_ocdid: str, fold: CardFold
) -> ReviewSummary:
    """The card summary, from a fold a caller already has.

    Split from `review_summary_for_changeset` so a page of cards folds once per card rather
    than once for its rows and again for its summary.
    """
    role_config = RoleConfig(roles=await get_roles())
    unique_role_ids = {
        fold.taxonomy.role_ids[label]
        for label in get_unique_roles(role_config)
        if label in fold.taxonomy.role_ids
    }
    role_labels = {role_id: label for label, role_id in fold.taxonomy.role_ids.items()}

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        read_organization_ids = set(
            await source_records.organizations_for_changeset(cur, changeset_id)
        )

    published, proposed = fold.published, fold.proposed
    if not read_organization_ids:
        # A hand edit records evidence only for what it adds; a changeset that read no page is
        # bounded by the organizations its own roster fills, the fallback `publish` uses.
        read_organization_ids = {
            membership.post.organization_id
            for person in proposed.people
            for membership in person.memberships
        }
    unverified = await _unverified_post_issues([jurisdiction_ocdid])
    names = await _organization_names_for(read_organization_ids)
    return fold_card_summary(
        published,
        proposed,
        roster_diff(published, proposed),
        read_organization_ids,
        role_labels,
        unique_role_ids,
        unverified.get(jurisdiction_ocdid, []),
        names,
    )


async def _organization_names_for(organization_ids: set[str]) -> dict[str, str]:
    if not organization_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await organizations_db.names(cur, sorted(organization_ids))


async def _unverified_post_issues(
    jurisdiction_ocdids: list[str],
) -> dict[str, list[Issue]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        unverified = await posts_db.unverified_by_jurisdiction(cur, jurisdiction_ocdids)
    return {ocdid: unverified_post_issues(posts) for ocdid, posts in unverified.items()}
