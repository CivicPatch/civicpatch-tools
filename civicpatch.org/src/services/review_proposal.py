"""What a scrape would change, for the review screen.

Orchestration only: the diff is `core.membership_proposal`, pure and tested there. This reads
the rosters and the memberships we already hold, and hands both to it.

Nothing is written. A post can be proposed; a membership is only true once accepted.
"""

from core.membership_proposal import ExistingMembership, ProposedChange, propose
from core.post_derivation import derived_posts
from core.post_issues import append_post_issues, unverified_post_issues
from database import assertions
from database import memberships as memberships_db
from database import posts as posts_db
from database import requests as requests_db
from database.database import get_pool
from database.pipeline_runs import get_pipeline_run_result
from schemas.assertions import EntityType
from database.roles import get_roles
from services.publish import chosen_posts
from shared.schemas import Issue, Person, RoleConfig
from shared.utils.taxonomy import build_taxonomy


async def review_summary_for_request(request_id: str) -> dict:
    """The stored summary, plus the issues computed from posts.

    Appended at read time rather than written beside the rest: a post nobody has vouched for
    belongs to the jurisdiction, so it outlives the scrape that minted it and cannot live in
    that scrape's summary. Dismissing a scrape is not an answer to the post it raised.
    """
    result = await get_pipeline_run_result(request_id)
    if not result:
        return {}
    posts = await _unverified_post_issues(result["jurisdiction_ocdid"])
    return append_post_issues(result.get("review_json") or {}, posts)


async def _unverified_post_issues(jurisdiction_ocdid: str) -> list[Issue]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        unverified = await posts_db.unverified_by_jurisdiction(cur, [jurisdiction_ocdid])
    return unverified_post_issues(unverified[jurisdiction_ocdid])


async def proposals_for_requests(
    request_ids: list[str],
) -> dict[str, list[ProposedChange]]:
    """One taxonomy build and one membership read per jurisdiction, whatever the page size."""
    rosters = await requests_db.get_request_rosters(request_ids)
    if not rosters:
        return {}

    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    ocdids = {roster["jurisdiction_ocdid"] for roster in rosters.values()}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        held = await memberships_db.open_by_jurisdiction(cur, list(ocdids))

    proposals: dict[str, list[ProposedChange]] = {}
    for request_id, roster in rosters.items():
        ocdid = roster["jurisdiction_ocdid"]
        people = [
            Person(**{**person, "jurisdiction_ocdid": ocdid})
            for person in roster["data_json"]
        ]
        proposals[request_id] = propose(
            derived_posts(people, taxonomy, roles, await chosen_posts(people)),
            [ExistingMembership(**row) for row in held[ocdid]],
        )
    return proposals


async def assertions_for_people(person_ids: list[str]) -> dict[str, list[dict]]:
    """Every assertion about these people, for the editor's per-field tags."""
    if not person_ids:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await assertions.list_for_entities(cur, EntityType.PERSON, person_ids)
