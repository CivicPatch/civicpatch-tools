"""What a scrape would change, for the review screen.

Orchestration only: the diff is `core.membership_proposal`, pure and tested there. This reads
the rosters and the memberships we already hold, and hands both to it.

Nothing is written. A post can be proposed; a membership is only true once accepted.
"""

from core.membership_proposal import ExistingMembership, ProposedChange, propose
from core.post_derivation import derived_posts
from database import memberships as memberships_db
from database import requests as requests_db
from database.database import get_pool
from database.roles import get_roles
from shared.schemas import Official, RoleConfig
from shared.utils.taxonomy import build_taxonomy


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
        officials = [
            Official(**{**person, "jurisdiction_ocdid": ocdid})
            for person in roster["data_json"]
        ]
        proposals[request_id] = propose(
            derived_posts(officials, taxonomy, roles),
            [ExistingMembership(**row) for row in held[ocdid]],
        )
    return proposals
