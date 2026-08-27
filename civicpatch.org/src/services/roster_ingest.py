"""Turning a source's rows into an identified roster.

Shared by the two producers that have one: the pipeline's artifact submit
(`people_collector`) and the curated-sheet import. Both hand over rows and get back people who
already carry the id we know them by — matching is ingest's job, so neither source has to
report one.

They differ only in where `identities` comes from, which is why that is a parameter: the
pipeline can fall back to its research step for a jurisdiction we have never published, and a
sheet has no analogue.
"""

import logging

from core.people_roster import identified, records_by_person, roster_from_rows
from core.post_derivation import DerivedPost, SourcedPerson, derived_posts
from database import posts as posts_db
from database.people import get_person_models
from services.publish import chosen_posts
from shared.utils.name_utils import person_list_to_identities
from shared.schemas import Person, Role
from shared.utils.person_id_utils import resolve_people_ids
from shared.utils.taxonomy import Taxonomy

logger = logging.getLogger(__name__)


async def published_identities(jurisdiction_ocdid: str) -> dict:
    """The prior reconciliation groups against: our own published people."""
    existing = await get_person_models(jurisdiction_ocdid)
    return person_list_to_identities(existing) if existing else {}


async def assign_ids(jurisdiction_ocdid: str, roster: list[dict]) -> list[dict]:
    """Give every person the id we already know them by, or a fresh one.

    Everyone, not only the entries arriving without one: `resolve_people_ids` guards against
    two entries claiming one person, and only sees the collision if it sees both. Matched
    against inactive people too, so someone returning after a term away keeps their id.
    """
    everyone = await get_person_models(jurisdiction_ocdid)
    resolutions = resolve_people_ids(
        roster, everyone, person_list_to_identities(everyone)
    )
    return [
        identified(person, resolution)
        for person, resolution in zip(roster, resolutions)
    ]


async def reconcile_roster(
    jurisdiction_ocdid: str,
    rows: list[dict],
    identities: dict,
    taxonomy: Taxonomy,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """The roster a source's rows mean, and the records behind each of its people.

    Fatal on failure, unlike the writes that follow it: everything downstream consumes this.
    """
    roster, records_by_name = roster_from_rows(
        rows, identities, taxonomy, jurisdiction_ocdid, logger
    )
    identified_roster = await assign_ids(jurisdiction_ocdid, roster)
    return identified_roster, records_by_person(identified_roster, records_by_name)


async def derive_and_store_posts(
    request_id: str,
    jurisdiction_ocdid: str,
    roster: list[dict],
    roles: list[Role],
    taxonomy: Taxonomy,
) -> list[DerivedPost]:
    """Mint the seats this roster's labels imply.

    Raises: both callers want the failure but do different things with it, so the policy stays
    with them. `chosen_posts` is empty at ingest and returns without a query, but a re-submit of
    an edited roster must not undo a reviewer's pick.
    """
    people = [Person(**person) for person in roster]
    sourced = [SourcedPerson.from_person(person) for person in people]
    derived = derived_posts(sourced, taxonomy, roles, await chosen_posts(people))
    await posts_db.find_or_create_all(jurisdiction_ocdid, derived, request_id)
    return derived
