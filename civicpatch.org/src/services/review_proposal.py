"""What a scrape would change, for the review screen.

Orchestration only: the diff is `core.membership_proposal`, pure and tested there. This reads
the rosters and the memberships we already hold, and hands both to it.

Nothing is written. A post can be proposed; a membership is only true once accepted.
"""

import asyncio

from core.membership_proposal import ExistingMembership, ProposedChange, propose
from core.post_derivation import derived_posts
from core.post_issues import (
    append_post_issues,
    disputed_post_issues,
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
from shared.schemas import POST_FIELD, Issue, OpenStatesRecord, Person, RoleConfig
from shared.utils.config_utils import get_unique_roles
from shared.utils.name_utils import person_list_to_identities
from shared.utils.review_utils import ReviewInputs, build_review_summary
from shared.utils.taxonomy import build_taxonomy


async def review_summary_for_request(changeset_id: str) -> dict:

    jurisdiction_ocdid = await changesets_db.get_request_jurisdiction(changeset_id)
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
            *disputed_post_issues(changes, picked),
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
    ocdids = await changesets_db.jurisdictions_for_requests(changeset_ids)
    if not ocdids:
        return {}
    # The post lookup is org-scoped, because `posts_identity_uq` is. A changeset naming no
    # organization has never published, so it has no posts to find either.
    organizations = await changesets_db.organizations_for_changesets(changeset_ids)
    if rosters is None:
        rosters = await proposed_rosters(changeset_ids)

    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        jurisdictions = list(set(ocdids.values()))
        held = await memberships_db.open_by_jurisdiction(cur, jurisdictions)
        post_ids = await posts_db.ids_by_identity(
            cur, list(set(organizations.values()))
        )

    proposals: dict[str, list[ProposedChange]] = {}
    for changeset_id, ocdid in ocdids.items():
        people = [
            OpenStatesRecord(**{**person, "jurisdiction_ocdid": ocdid})
            for person in rosters.get(changeset_id, [])
        ]
        proposals[changeset_id] = [
            change.model_copy(
                update={
                    "post_id": (
                        post_ids.get(
                            (organization_id, change.role_id, change.division_ocdid)
                        )
                        if (organization_id := organizations.get(changeset_id))
                        else None
                    )
                }
            )
            for change in propose(
                derived_posts(
                    people,
                    taxonomy,
                    roles,
                    await chosen_posts(picks_in(people)),
                ),
                [ExistingMembership(**row) for row in held[ocdid]],
            )
        ]
    return proposals


async def assertions_for_people(person_ids: list[str]) -> dict[str, list[dict]]:
    """Every assertion about these people, for the editor's per-field tags."""
    if not person_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await assertions.list_for_entities(cur, EntityType.PERSON, person_ids)
