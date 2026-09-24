"""What a scrape would change, for the review screen.

Orchestration only: the diff is `core.membership_proposal`, pure and tested there. This reads
the rosters and the memberships we already hold, and hands both to it.

Nothing is written. A post can be proposed; a membership is only true once accepted.
"""


from core.membership_proposal import ExistingMembership, ProposedChange, propose
from core.post_derivation import RosterEntry, derived_posts
from database import source_records
from database import changesets as changesets_db
from database import memberships as memberships_db
from database import posts as posts_db
from database.database import get_pool
from database.roles import get_roles
from services.publish import chosen_posts, picks_in
from services.roster import proposed_rosters
from shared.schemas import RoleConfig
from shared.utils.taxonomy import build_taxonomy


async def proposals_for_requests(
    changeset_ids: list[str],
    rosters: dict[str, list[dict]] | None = None,
) -> dict[str, list[ProposedChange]]:
    """One taxonomy build and one membership read per jurisdiction, whatever the page size.

    `rosters` is for a caller that already derived them — deriving a roster is the expensive
    half, and the summary reads the same one to diff against what we publish.
    """
    ocdids = await changesets_db.jurisdictions_for_changesets(changeset_ids)
    if not ocdids:
        return {}
    if rosters is None:
        rosters = await proposed_rosters(changeset_ids)

    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    jurisdictions = list(set(ocdids.values()))
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        held = await memberships_db.open_memberships(cur, jurisdictions)
        read_by_changeset = {
            changeset_id: await source_records.organizations_for_changeset(
                cur, changeset_id
            )
            for changeset_id in ocdids
        }

    held_by_jurisdiction: dict[str, list[ExistingMembership]] = {
        ocdid: [] for ocdid in jurisdictions
    }
    for membership in held:
        held_by_jurisdiction[membership.jurisdiction_ocdid].append(membership)

    changes_by_changeset: dict[str, list[ProposedChange]] = {}
    for changeset_id, ocdid in ocdids.items():
        people = [
            RosterEntry(**{**person, "jurisdiction_ocdid": ocdid})
            for person in rosters.get(changeset_id, [])
        ]
        derived = derived_posts(
            people, taxonomy, roles, await chosen_posts(picks_in(people))
        )
        # Same fallback as publish: a hand edit records evidence only for what it adds, so a
        # changeset with none is bounded by the organizations its own roster fills.
        read = read_by_changeset.get(changeset_id) or [
            post.organization_id for post in derived
        ]
        changes_by_changeset[changeset_id] = propose(
            derived, held_by_jurisdiction[ocdid], read
        )

    organization_ids = list(
        {
            change.organization_id
            for changes in changes_by_changeset.values()
            for change in changes
        }
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        post_ids = await posts_db.ids_by_identity(cur, organization_ids)
        names = await posts_db.asserted_labels(cur, list(post_ids.values()))

    return {
        changeset_id: [
            _with_existing_post(change, post_ids, names) for change in changes
        ]
        for changeset_id, changes in changes_by_changeset.items()
    }


def _with_existing_post(
    change: ProposedChange,
    post_ids: dict[tuple[str, str, str], str],
    names: dict[str, str],
) -> ProposedChange:
    """The proposed post's id and asserted name, when the post already exists."""
    post_id = post_ids.get(
        (change.organization_id, change.post.role_id, change.post.division_ocdid)
    )
    if post_id is None:
        return change
    label = names.get(post_id) or change.post.label
    return change.model_copy(
        update={"post": change.post.model_copy(update={"id": post_id, "label": label})}
    )
