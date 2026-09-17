"""What a scrape would change, for the review screen.

Orchestration only: the diff is `core.membership_proposal`, pure and tested there. This reads
the rosters and the memberships we already hold, and hands both to it.

Nothing is written. A post can be proposed; a membership is only true once accepted.
"""

import asyncio

from core.people_edits import SURFACED_FIELDS

from core.membership_proposal import ExistingMembership, ProposedChange, propose
from core.post_derivation import RosterEntry, derived_posts
from core.post_issues import (
    append_post_issues,
    moved_person_issues,
    unverified_post_issues,
)
from database import assertions
from database import changesets as changesets_db
from database import memberships as memberships_db
from database import people as people_db
from database import posts as posts_db
from database.database import get_pool
from database.roles import get_roles
from schemas.assertions import EntityType
from services.publish import chosen_posts, picks_in
from services.roster import proposed_roster, proposed_rosters
from shared.schemas import POST_FIELD, Issue, Person, RoleConfig
from shared.utils.config_utils import get_unique_roles
from shared.utils.name_utils import person_list_to_identities
from shared.utils.review_utils import ReviewInputs, build_review_summary
from shared.utils.taxonomy import build_taxonomy


async def review_summary_for_changeset(changeset_id: str) -> dict:

    jurisdiction_ocdid = await changesets_db.get_changeset_jurisdiction(changeset_id)
    if not jurisdiction_ocdid:
        return {}

    published, proposed, roles = await asyncio.gather(
        people_db.get_roster(jurisdiction_ocdid=jurisdiction_ocdid),
        proposed_roster(changeset_id, jurisdiction_ocdid),
        get_roles(),
    )
    summary = build_review_summary(
        published,
        proposed,
        ReviewInputs(
            identities=person_list_to_identities([Person(**p) for p in published]),
            unique_roles=get_unique_roles(RoleConfig(roles=roles)),
            changed_field_names=list(SURFACED_FIELDS),
        ),
    )
    summary["issues"] = [issue.model_dump() for issue in summary["issues"]]
    posts = await _unverified_post_issues(jurisdiction_ocdid)
    changes = (
        await proposals_for_requests([changeset_id], {changeset_id: proposed})
    ).get(changeset_id, [])
    # `proposed` has already been collapsed to this changeset's organization, so a `post_id`
    # here is the pick that applies to the review in front of the reviewer.
    picked = {
        person["id"]: post_id
        for person in proposed
        if (post_id := person.get(POST_FIELD))
    }
    return append_post_issues(
        summary,
        [
            *posts,
            *moved_person_issues(changes, picked),
        ],
    )


async def _unverified_post_issues(jurisdiction_ocdid: str) -> list[Issue]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        unverified = await posts_db.unverified_by_jurisdiction(
            cur, [jurisdiction_ocdid]
        )
    return unverified_post_issues(unverified[jurisdiction_ocdid])


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

    held_by_jurisdiction: dict[str, list[ExistingMembership]] = {ocdid: [] for ocdid in jurisdictions}
    for membership in held:
        held_by_jurisdiction[membership.jurisdiction_ocdid].append(membership)

    changes_by_changeset: dict[str, list[ProposedChange]] = {}
    for changeset_id, ocdid in ocdids.items():
        people = [
            RosterEntry(**{**person, "jurisdiction_ocdid": ocdid})
            for person in rosters.get(changeset_id, [])
        ]
        changes_by_changeset[changeset_id] = propose(
            derived_posts(people, taxonomy, roles, await chosen_posts(picks_in(people))),
            held_by_jurisdiction[ocdid],
        )

    organization_ids = list(
        {change.organization_id for changes in changes_by_changeset.values() for change in changes}
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        post_ids = await posts_db.ids_by_identity(cur, organization_ids)

    return {
        changeset_id: [
            change.model_copy(
                update={
                    "post_id": post_ids.get(
                        (change.organization_id, change.role_id, change.division_ocdid)
                    )
                }
            )
            for change in changes
        ]
        for changeset_id, changes in changes_by_changeset.items()
    }


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
