import asyncio
import logging

from core.people_edits import with_stated_values
from core.people_roster import roster_from_sightings
from database import assertions
from database import changesets as changesets_db
from database.database import get_pool
from database.people import get_people_by_ids
from database.roles import get_roles
from database import changesets as changesets_db
from database import posts as posts_db
from database.source_records import get_source_records_for_changeset
from schemas.assertions import EntityType
from shared.schemas import POST_FIELD, RoleConfig
from shared.utils.taxonomy import build_taxonomy

logger = logging.getLogger(__name__)


async def _roster(changeset_id: str, jurisdiction_ocdid: str) -> tuple[list[dict], dict]:
    sightings = await get_source_records_for_changeset(changeset_id)
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


async def proposed_roster(changeset_id: str, jurisdiction_ocdid: str) -> list[dict]:
    roster, stated = await _roster(changeset_id, jurisdiction_ocdid)
    return await _one_post_each(
        changeset_id,
        [with_stated_values(person, stated.get(person["id"], {})) for person in roster],
    )


async def _one_post_each(changeset_id: str, people: list[dict]) -> list[dict]:
    """Collapse each person's accepted posts to the one this review is about.

    Picks are stored per post because a person holds one per organization (see `LIST_FIELDS`).
    A review is about a single body, so exactly one of them can apply here — and the editor
    binds one value, because the reviewer is choosing one membership.
    """
    accepted = {
        person["id"]: posts
        for person in people
        if isinstance(posts := person.get(POST_FIELD), list) and posts
    }
    if not accepted:
        return people

    organization_id = (
        await changesets_db.organizations_for_changesets([changeset_id])
    ).get(changeset_id)
    every_id = sorted({post_id for posts in accepted.values() for post_id in posts})

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        here = await posts_db.ids_in_organization(cur, every_id, organization_id or "")

    return [
        {**person, POST_FIELD: next(
            (post_id for post_id in accepted.get(person["id"], []) if post_id in here),
            None,
        )}
        if person["id"] in accepted
        else person
        for person in people
    ]


async def scraped_roster(changeset_id: str, jurisdiction_ocdid: str) -> list[dict]:
    roster, _ = await _roster(changeset_id, jurisdiction_ocdid)
    return roster


# One roster holds two pool connections at its widest, and the pool is 20. An unbounded gather
# over a bulk import's forty requests therefore asks for more than exists and every one of them
# waits out the timeout instead. The overlap is worth little — the work is CPU — so a small
# window keeps what it was for without the failure mode.
_ROSTER_CONCURRENCY = 4


async def proposed_rosters(changeset_ids: list[str]) -> dict[str, list[dict]]:
    """One roster per request, for a page of review cards.

    Derived per request rather than in one query: a roster is Python over that scrape's own
    sightings, so there is nothing to batch.
    """
    if not changeset_ids:
        return {}
    ocdids = await changesets_db.jurisdictions_for_changesets(changeset_ids)
    limit = asyncio.Semaphore(_ROSTER_CONCURRENCY)

    async def one(changeset_id: str, ocdid: str) -> list[dict]:
        async with limit:
            return await proposed_roster(changeset_id, ocdid)

    rosters = await asyncio.gather(
        *[one(changeset_id, ocdid) for changeset_id, ocdid in ocdids.items()]
    )
    return dict(zip(ocdids, rosters))
