"""What a scrape would change, for the review screen.

Orchestration only: the diff is `core.membership_proposal`, pure and tested there. This reads
the rosters and the memberships we already hold, and hands both to it.

Nothing is written. A post can be proposed; a membership is only true once accepted.
"""

import asyncio

from core.membership_proposal import ExistingMembership, ProposedChange, propose
from core.post_derivation import RosterEntry, derived_posts
from core.post_issues import unverified_post_issues
from core.review_summary import ReviewSummary, build_card_summary
from database import assertions
from database import changesets as changesets_db
from database import memberships as memberships_db
from database import organizations as organizations_db
from database import people as people_db
from database import posts as posts_db
from database import source_records
from database.database import get_pool
from database.roles import get_roles
from schemas.assertions import EntityType
from services.publish import chosen_posts, picks_in
from services.roster import proposed_rosters
from shared.schemas import Issue, RoleConfig
from shared.utils.config_utils import get_unique_roles
from shared.utils.taxonomy import build_taxonomy


async def review_summary_for_changeset(changeset_id: str) -> ReviewSummary:
    jurisdiction_ocdid = await changesets_db.get_changeset_jurisdiction(changeset_id)
    if not jurisdiction_ocdid:
        return ReviewSummary()
    rosters = await proposed_rosters([changeset_id])
    changes = await proposals_for_requests([changeset_id], rosters)
    published = await people_db.get_rosters_by_jurisdiction([jurisdiction_ocdid])
    summaries = await review_summaries([changeset_id], published, rosters, changes)
    return summaries[changeset_id]


async def review_summaries(
    changeset_ids: list[str],
    published: dict[str, list[dict]],
    rosters: dict[str, list[dict]],
    changes: dict[str, list[ProposedChange]],
) -> dict[str, ReviewSummary]:
    """The card summary for each changeset, with one read of each kind for all of them.

    `published` is keyed by jurisdiction, as `people.get_rosters_by_jurisdiction` returns it.
    """
    if not changeset_ids:
        return {}
    ocdids = await changesets_db.jurisdictions_for_changesets(changeset_ids)
    jurisdictions = list(set(ocdids.values()))
    every_change = [change for listed in changes.values() for change in listed]
    roles, unverified, names = await asyncio.gather(
        get_roles(),
        _unverified_post_issues(jurisdictions),
        _organization_names(every_change),
    )
    unique_roles = get_unique_roles(RoleConfig(roles=roles))
    return {
        changeset_id: build_card_summary(
            published.get(ocdid, []),
            rosters.get(changeset_id, []),
            changes.get(changeset_id, []),
            unique_roles,
            unverified.get(ocdid, []),
            names,
        )
        for changeset_id, ocdid in ocdids.items()
    }


async def _organization_names(changes: list[ProposedChange]) -> dict[str, str]:
    """An issue names the organization, and a proposal carries only its id."""
    ids = list({change.organization_id for change in changes})
    if not ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await organizations_db.names(cur, ids)


async def _unverified_post_issues(jurisdiction_ocdids: list[str]) -> dict[str, list[Issue]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        unverified = await posts_db.unverified_by_jurisdiction(cur, jurisdiction_ocdids)
    return {ocdid: unverified_post_issues(posts) for ocdid, posts in unverified.items()}


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
            changeset_id: await source_records.organizations_for_changeset(cur, changeset_id)
            for changeset_id in ocdids
        }

    held_by_jurisdiction: dict[str, list[ExistingMembership]] = {ocdid: [] for ocdid in jurisdictions}
    for membership in held:
        held_by_jurisdiction[membership.jurisdiction_ocdid].append(membership)

    changes_by_changeset: dict[str, list[ProposedChange]] = {}
    for changeset_id, ocdid in ocdids.items():
        people = [
            RosterEntry(**{**person, "jurisdiction_ocdid": ocdid})
            for person in rosters.get(changeset_id, [])
        ]
        derived = derived_posts(people, taxonomy, roles, await chosen_posts(picks_in(people)))
        # Same fallback as publish: a hand edit records evidence only for what it adds, so a
        # changeset with none is bounded by the organizations its own roster fills.
        read = read_by_changeset.get(changeset_id) or [post.organization_id for post in derived]
        changes_by_changeset[changeset_id] = propose(
            derived, held_by_jurisdiction[ocdid], read
        )

    organization_ids = list(
        {change.organization_id for changes in changes_by_changeset.values() for change in changes}
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        post_ids = await posts_db.ids_by_identity(cur, organization_ids)
        names = await posts_db.asserted_labels(cur, list(post_ids.values()))

    return {
        changeset_id: [_with_existing_post(change, post_ids, names) for change in changes]
        for changeset_id, changes in changes_by_changeset.items()
    }


def _with_existing_post(
    change: ProposedChange,
    post_ids: dict[tuple[str, str, str], str],
    names: dict[str, str],
) -> ProposedChange:
    """The proposed post's id and asserted name, when the post already exists."""
    post_id = post_ids.get((change.organization_id, change.post.role_id, change.post.division_ocdid))
    if post_id is None:
        return change
    label = names.get(post_id) or change.post.label
    return change.model_copy(
        update={"post": change.post.model_copy(update={"id": post_id, "label": label})}
    )


async def assertions_for_people(person_ids: list[str]) -> dict[str, list[dict]]:
    """Every assertion about these people, for the editor's per-field tags.

    A membership label's assertion is filed against the membership, not the person
    (`set_label`) — merged in here, under the person it belongs to, so the editor's
    per-field lock lookup never has to know the label lives on a different entity.
    """
    if not person_ids:
        return {}
    pool = await get_pool()

    async def _person_claims() -> dict[str, list[dict]]:
        async with pool.connection() as conn, conn.cursor() as cur:
            return await assertions.list_for_entities(cur, EntityType.PERSON, person_ids)

    async def _open_memberships() -> list[dict]:
        async with pool.connection() as conn, conn.cursor() as cur:
            return await memberships_db.open_membership_ids_for_persons(cur, person_ids)

    # Independent reads — neither needs the other's result — so they run concurrently rather
    # than as two round trips on one connection.
    claims, open_memberships = await asyncio.gather(_person_claims(), _open_memberships())
    if not open_memberships:
        return claims
    membership_ids = [row["id"] for row in open_memberships]
    person_by_membership = {row["id"]: row["person_id"] for row in open_memberships}
    async with pool.connection() as conn, conn.cursor() as cur:
        membership_claims = await assertions.list_for_entities(
            cur, EntityType.MEMBERSHIP, membership_ids
        )
    for membership_id, membership_assertions in membership_claims.items():
        person_id = person_by_membership[membership_id]
        claims.setdefault(person_id, []).extend(membership_assertions)
    return claims
