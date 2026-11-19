"""A review card's data, loaded for many changesets at once.

Each page that lists cards chooses which changesets; this loads them.
"""

import asyncio
from typing import NamedTuple

from core.review_summary import ReviewSummary
from core.source_pages import CachedPage
from database import changesets as changesets_db
from database import pipeline_runs as pipeline_runs_db
from database import post_listings as post_listings_db
from database import source_pages as source_pages_db
from schemas.review_cards import ReviewCard
from services.claims import claims_for_people
from services.review_summary import summary_of
from services.review_sources import build_sources, cached_pages_for
from services.roster import ROSTERS_AT_A_TIME, CardSides, card_fold, sides_of
from shared.utils.batching import gather_in_batches


class CardParts(NamedTuple):
    """One card's own reads, before the page-wide ones join them."""

    changeset_id: str
    jurisdiction_ocdid: str
    sides: CardSides
    review: ReviewSummary


async def with_card_data(changeset_ids: list[str]) -> list[ReviewCard]:
    """One card per changeset we hold, in the order given — an unknown id is skipped."""
    if not changeset_ids:
        return []
    ocdids = await changesets_db.jurisdictions_for_changesets(changeset_ids)
    known = [changeset_id for changeset_id in changeset_ids if changeset_id in ocdids]
    parts = await gather_in_batches(
        known,
        ROSTERS_AT_A_TIME,
        lambda changeset_id: _parts_of(changeset_id, ocdids[changeset_id]),
    )
    everyone = [
        person_id for part in parts for person_id in _person_ids(part.sides.existing)
    ]
    # A card's own run's cached pages are only known once its run is, so that read comes first.
    run_ids = await pipeline_runs_db.pipeline_run_ids_for_changesets(known)
    # One read each for the whole page rather than a round trip per card.
    organizations, claims, cached_pages, organizations_read = await asyncio.gather(
        post_listings_db.list_by_organization_for_jurisdictions(list(set(ocdids.values()))),
        claims_for_people(everyone),
        source_pages_db.get_cached_pages(
            list(set(ocdids.values())), list(run_ids.values())
        ),
        source_pages_db.organizations_read_by_changesets(known),
    )
    return [
        _card(part, organizations, claims, run_ids, cached_pages, organizations_read)
        for part in parts
    ]


async def _parts_of(changeset_id: str, jurisdiction_ocdid: str) -> CardParts:
    """One fold pair, read three ways: the card's rows, its override disclosure and its
    summary are the same question asked differently, so they share a fold."""
    fold = await card_fold(changeset_id, jurisdiction_ocdid)
    return CardParts(
        changeset_id=changeset_id,
        jurisdiction_ocdid=jurisdiction_ocdid,
        sides=sides_of(fold, jurisdiction_ocdid),
        review=await summary_of(changeset_id, jurisdiction_ocdid, fold),
    )


def _card(
    part: CardParts,
    organizations: dict[str, list[dict]],
    claims: dict[str, list[dict]],
    run_ids: dict[str, str],
    cached_pages: list[CachedPage],
    organizations_read: dict[str, list[str]],
) -> ReviewCard:
    pipeline_run_id = run_ids.get(part.changeset_id)
    sources = build_sources(
        cached_pages_for(cached_pages, part.jurisdiction_ocdid, pipeline_run_id),
        _source_urls(part.sides.proposed),
        pipeline_run_id,
    )
    return ReviewCard(
        changeset_id=part.changeset_id,
        jurisdiction_ocdid=part.jurisdiction_ocdid,
        existing=part.sides.existing,
        proposed=part.sides.proposed,
        sources=sources,
        overridden_source_values=part.sides.overridden,
        review=part.review,
        organizations=organizations.get(part.jurisdiction_ocdid, []),
        organizations_read=organizations_read.get(part.changeset_id, []),
        claims={
            person_id: claims[person_id]
            for person_id in _person_ids(part.sides.existing)
            if person_id in claims
        },
    )


def _source_urls(roster: list[dict]) -> list[str]:
    return list({url for person in roster for url in (person.get("source_urls") or [])})


def _person_ids(roster: list[dict]) -> list[str]:
    return [person["id"] for person in roster if person.get("id")]
