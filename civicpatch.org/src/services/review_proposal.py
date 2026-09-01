"""What a scrape would change, for the review screen.

Orchestration only: the diff is `core.membership_proposal`, pure and tested there. This reads
the rosters and the memberships we already hold, and hands both to it.

Nothing is written. A post can be proposed; a membership is only true once accepted.
"""

import asyncio

from core.membership_proposal import ExistingMembership, ProposedChange, propose
from core.post_derivation import SourcedPerson, derived_posts
from core.post_issues import (
    append_post_issues,
    moved_person_issues,
    unverified_post_issues,
)
from database import assertions
from database import memberships as memberships_db
from database import posts as posts_db
from database import people as people_db
from database import changesets as changesets_db
from database.database import get_pool
from schemas.assertions import EntityType
from database.roles import get_roles
from services.publish import chosen_posts
from services.roster import proposed_roster, proposed_rosters
from shared.schemas import Issue, Person, RoleConfig
from shared.utils.config_utils import get_unique_roles
from shared.utils.name_utils import person_list_to_identities
from shared.utils.review_utils import ReviewInputs, build_review_summary
from shared.utils.taxonomy import build_taxonomy


async def review_summary_for_request(request_id: str) -> dict:
    """What a reviewer needs to look at, computed now rather than read back.

    The baseline is the roster we publish, not the scrape's own research step — that lived
    only in the workflow context, which is why the summary used to be frozen at ingest. Both
    sides are already read for the card, so this costs nothing the page was not paying.

    Post issues are appended rather than computed with the rest: a post nobody has vouched for
    belongs to the jurisdiction, so it outlives the scrape that minted it. A seat move joins
    them for a different reason — `build_review_summary` compares two rosters, and which seat
    someone lands in is not on a roster, it is the derivation's answer.
    """
    jurisdiction_ocdid = await changesets_db.get_request_jurisdiction(request_id)
    if not jurisdiction_ocdid:
        return {}

    published, proposed, roles = await asyncio.gather(
        people_db.get_roster(jurisdiction_ocdid=jurisdiction_ocdid),
        proposed_roster(request_id, jurisdiction_ocdid),
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
        await proposals_for_requests([request_id], {request_id: proposed})
    ).get(request_id, [])
    return append_post_issues(summary, [*posts, *moved_person_issues(changes)])


async def _unverified_post_issues(jurisdiction_ocdid: str) -> list[Issue]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        unverified = await posts_db.unverified_by_jurisdiction(cur, [jurisdiction_ocdid])
    return unverified_post_issues(unverified[jurisdiction_ocdid])


async def proposals_for_requests(
    request_ids: list[str],
    rosters: dict[str, list[dict]] | None = None,
) -> dict[str, list[ProposedChange]]:
    """One taxonomy build and one membership read per jurisdiction, whatever the page size.

    `rosters` is for a caller that already derived them — deriving a roster is the expensive
    half, and the summary reads the same one to diff against what we publish.
    """
    ocdids = await changesets_db.jurisdictions_for_requests(request_ids)
    if not ocdids:
        return {}
    if rosters is None:
        rosters = await proposed_rosters(request_ids)

    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        jurisdictions = list(set(ocdids.values()))
        held = await memberships_db.open_by_jurisdiction(cur, jurisdictions)
        post_ids = await posts_db.ids_by_identity(cur, jurisdictions)

    proposals: dict[str, list[ProposedChange]] = {}
    for request_id, ocdid in ocdids.items():
        people = [
            Person(**{**person, "jurisdiction_ocdid": ocdid})
            for person in rosters.get(request_id, [])
        ]
        proposals[request_id] = [
            change.model_copy(
                update={
                    "post_id": post_ids.get(
                        (ocdid, change.role_id, change.division_ocdid)
                    )
                }
            )
            for change in propose(
                derived_posts(
                    [SourcedPerson.from_person(person) for person in people],
                    taxonomy,
                    roles,
                    await chosen_posts(people),
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
