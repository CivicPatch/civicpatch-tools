import asyncio
import logging

from core.people_edits import with_stated_values
from core.people_roster import roster_from_sightings
from database import assertions
from database import requests as requests_db
from database.database import get_pool
from database.people import get_people_by_ids
from database.roles import get_roles
from database.source_records import get_source_records_for_request
from schemas.assertions import EntityType
from shared.schemas import RoleConfig
from shared.utils.taxonomy import build_taxonomy

logger = logging.getLogger(__name__)


async def _roster(request_id: str, jurisdiction_ocdid: str) -> tuple[list[dict], dict]:
    sightings = await get_source_records_for_request(request_id)
    if not sightings:
        return [], {}

    person_ids = list({sighting["person_id"] for sighting in sightings})
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        published, roles, stated = await asyncio.gather(
            get_people_by_ids(person_ids),
            get_roles(),
            assertions.stated_values(cur, EntityType.PERSON, person_ids),
        )
    return roster_from_sightings(
        sightings,
        published,
        build_taxonomy(RoleConfig(roles=roles)),
        jurisdiction_ocdid,
        logger,
    ), stated


async def proposed_roster(request_id: str, jurisdiction_ocdid: str) -> list[dict]:
    roster, stated = await _roster(request_id, jurisdiction_ocdid)
    return [
        with_stated_values(person, stated.get(person["id"], {})) for person in roster
    ]


async def scraped_roster(request_id: str, jurisdiction_ocdid: str) -> list[dict]:
    roster, _ = await _roster(request_id, jurisdiction_ocdid)
    return roster


async def proposed_rosters(request_ids: list[str]) -> dict[str, list[dict]]:
    """One roster per request, for a page of review cards.

    Derived per request rather than in one query: a roster is Python over that scrape's own
    sightings, so there is nothing to batch. `gather` buys little — the work is CPU — but it
    keeps the two database reads per request overlapping.
    """
    if not request_ids:
        return {}
    ocdids = await requests_db.jurisdictions_for_requests(request_ids)
    rosters = await asyncio.gather(
        *[
            proposed_roster(request_id, ocdid)
            for request_id, ocdid in ocdids.items()
        ]
    )
    return dict(zip(ocdids, rosters))
