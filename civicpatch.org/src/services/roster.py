import asyncio
import logging
from datetime import datetime, timezone
from typing import NamedTuple

from core.display_rows import PostLabels, display_rows
from core.changeset_lifecycle import PARTIAL_KINDS
from core.people_edits import source_values_overridden, with_asserted_values
from core.people_roster import partial_roster, roster_from_sightings
from core.projection.diff import on_roster
from core.projection.facts import Facts
from core.projection.roster import Roster, overridden_by_person
from database import assertions, source_records
from database import changesets as changesets_db
from database import posts as posts_db
from database import projection as projection_db
from database.database import get_pool
from database.people import get_people_by_ids, get_roster
from database.roles import get_roles
from database.source_records import (
    get_earliest_source_records_for_people,
    get_source_records_for_changeset,
)
from schemas.assertions import EntityType
from shared.schemas import POST_FIELD, RoleConfig
from shared.utils.taxonomy import Taxonomy, build_taxonomy

logger = logging.getLogger(__name__)


async def _roster(
    changeset_id: str, jurisdiction_ocdid: str
) -> tuple[list[dict], dict]:
    sightings = await get_source_records_for_changeset(changeset_id)
    if not sightings:
        return [], {}

    person_ids = list({sighting["person_id"] for sighting in sightings})
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        published, roles, asserted = await asyncio.gather(
            get_people_by_ids(person_ids),
            get_roles(),
            assertions.asserted_values(cur, EntityType.PERSON, person_ids),
        )
    return roster_from_sightings(
        sightings,
        published,
        build_taxonomy(RoleConfig(roles=roles)),
        jurisdiction_ocdid,
        logger,
    ), asserted


async def origin_roster_for(
    entity_ids: list[str], jurisdiction_ocdid: str
) -> list[dict]:
    """These people's fields as their earliest sighting recorded them — the pristine base a
    rollback overlays currently-active assertions onto. Not the live roster: that already has
    every assertion (withdrawn ones included) baked in, so there's nothing left to fall back to.
    `published={}` deliberately — `canonical_name` would otherwise keep the live name over the
    sighting's, defeating the whole point."""
    sightings = await get_earliest_source_records_for_people(entity_ids)
    if not sightings:
        return []
    roles = await get_roles()
    return roster_from_sightings(
        sightings,
        {},
        build_taxonomy(RoleConfig(roles=roles)),
        jurisdiction_ocdid,
        logger,
    )


async def _fold_for_card(
    jurisdiction_ocdid: str, including: str | None
) -> tuple[list[dict], Facts, Taxonomy]:
    """One fold, and the facts behind it, for a caller that wants more than the rows."""
    taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        roster, facts = await projection_db.derived_roster_and_facts(
            cur, jurisdiction_ocdid, including=including, taxonomy=taxonomy
        )
        post_labels = await posts_db.asserted_labels_by_key(cur, jurisdiction_ocdid)
    rows = display_rows(on_roster(roster), jurisdiction_ocdid, taxonomy, post_labels)
    return rows, facts, taxonomy


async def published_card_rows(jurisdiction_ocdid: str) -> list[dict]:
    """The published roster as the card's `existing` rows, derived rather than read.

    `on_roster` is what `get_roster`'s `IS_ON_THE_ROSTER` was asking: somebody is on the roster
    if they hold a post. The shape is `PERSON_JSON`'s, so the browser reads the same keys.
    No override disclosure: the published side carries no locks, and working one out is a
    second pass over every record in the jurisdiction.
    """
    rows, _facts, _taxonomy = await _fold_for_card(jurisdiction_ocdid, None)
    return rows


class CardSides(NamedTuple):
    """What a review card compares: the roster today, the roster this changeset would make
    live, and the page values the proposed side's locks disclose."""

    existing: list[dict]
    proposed: list[dict]
    overridden: dict[str, dict]


class CardFold(NamedTuple):
    """Both sides of a card as the fold made them, before anything presents them.

    Every question a card answers — its rows, its override disclosure, its summary — is one of
    these two rosters read differently. Holding them means a caller answers all three from one
    pair of folds instead of a pair each.
    """

    published: Roster
    proposed: Roster
    proposed_facts: Facts
    taxonomy: Taxonomy
    # A post a human named. The fold cannot see these — naming a post is a claim on the POST
    # entity and `database/facts.py` does not load those until step 10 — so they overlay here.
    post_labels: PostLabels


async def card_fold(changeset_id: str, jurisdiction_ocdid: str) -> CardFold:
    """The roster today and the roster this changeset would make live, one connection, one
    `as_of`, one taxonomy.

    Pinned to a single moment on purpose: derived separately they would take a `now()` each,
    and a claim landing between them would reach one side of the card and not the other —
    which is `derived_roster`'s own warning. One connection because they are one question.
    """
    taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
    as_of = datetime.now(timezone.utc)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        published, _facts = await projection_db.derived_roster_and_facts(
            cur, jurisdiction_ocdid, as_of=as_of, taxonomy=taxonomy
        )
        proposed, proposed_facts = await projection_db.derived_roster_and_facts(
            cur,
            jurisdiction_ocdid,
            including=changeset_id,
            as_of=as_of,
            taxonomy=taxonomy,
        )
        post_labels = await posts_db.asserted_labels_by_key(cur, jurisdiction_ocdid)
    return CardFold(
        published=on_roster(published),
        proposed=on_roster(proposed),
        proposed_facts=proposed_facts,
        taxonomy=taxonomy,
        post_labels=post_labels,
    )


def sides_of(fold: CardFold, jurisdiction_ocdid: str) -> CardSides:
    return CardSides(
        existing=display_rows(
            fold.published, jurisdiction_ocdid, fold.taxonomy, fold.post_labels
        ),
        proposed=display_rows(
            fold.proposed, jurisdiction_ocdid, fold.taxonomy, fold.post_labels
        ),
        overridden=overridden_by_person(fold.proposed_facts),
    )


async def card_sides(changeset_id: str, jurisdiction_ocdid: str) -> CardSides:
    return sides_of(await card_fold(changeset_id, jurisdiction_ocdid), jurisdiction_ocdid)


async def proposed_roster(changeset_id: str, jurisdiction_ocdid: str) -> list[dict]:
    roster, _overridden = await proposed_roster_and_source_values(
        changeset_id, jurisdiction_ocdid
    )
    return roster


async def proposed_roster_and_source_values(
    changeset_id: str, jurisdiction_ocdid: str
) -> tuple[list[dict], dict[str, dict]]:
    """The roster a reviewer sees, and what the source said where an assertion changed it.

    Both from one pass: the pre-overlay roster is `_roster`'s own answer, so the second half
    costs nothing beyond the comparison. Asking for it separately would re-read every sighting.
    """
    roster, asserted = await _roster(changeset_id, jurisdiction_ocdid)
    overridden = {
        person["id"]: source_values
        for person in roster
        if (
            source_values := source_values_overridden(
                person, asserted.get(person["id"], {})
            )
        )
    }
    people = [
        with_asserted_values(person, asserted.get(person["id"], {}))
        for person in roster
    ]
    if await changesets_db.get_changeset_kind(changeset_id) in PARTIAL_KINDS:
        published = await get_roster(jurisdiction_ocdid=jurisdiction_ocdid)
        people = partial_roster(people, published)
    return await _one_post_each(changeset_id, people), overridden


async def _one_post_each(changeset_id: str, people: list[dict]) -> list[dict]:
    """Collapse each person's accepted posts to the one this review is about.

    Picks are stored per post because a person holds one per organization (see `LIST_FIELDS`).
    The ones that apply here are the ones in a body this changeset read a page for; the editor
    binds a single value, so a person picked in two of them keeps the first.
    """
    accepted = {
        person["id"]: posts
        for person in people
        if isinstance(posts := person.get(POST_FIELD), list) and posts
    }
    if not accepted:
        return people

    every_id = sorted({post_id for posts in accepted.values() for post_id in posts})

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_ids = await source_records.organizations_for_changeset(
            cur, changeset_id
        )
        here = await posts_db.ids_in_organizations(cur, every_id, organization_ids)

    return [
        {
            **person,
            POST_FIELD: next(
                (
                    post_id
                    for post_id in accepted.get(person["id"], [])
                    if post_id in here
                ),
                None,
            ),
        }
        if person["id"] in accepted
        else person
        for person in people
    ]


async def scraped_roster(changeset_id: str, jurisdiction_ocdid: str) -> list[dict]:
    roster, _ = await _roster(changeset_id, jurisdiction_ocdid)
    return roster


# One roster holds two pool connections at its widest, and the pool is 20 — see
# `gather_in_batches` for what an unbounded fan-out does to that. The overlap is worth little
# either way: the work is CPU.
ROSTERS_AT_A_TIME = 4

