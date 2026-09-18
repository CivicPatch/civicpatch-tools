"""A review card's data, loaded for many changesets at once.

Each page that lists cards chooses which changesets; this loads them.
"""

import asyncio

import database.people
import services.roster as services_roster
from core.review_summary import ReviewSummary
from database import changesets as changesets_db
from database import posts as posts_db
from schemas.review_cards import ReviewCard, ReviewSource
from services.review_proposal import (
    assertions_for_people,
    proposals_for_requests,
    review_summaries,
)
from services.review_sources import build_sources


async def with_card_data(changeset_ids: list[str]) -> list[ReviewCard]:
    """One card per changeset we hold, in the order given — an unknown id is skipped. One read of
    each kind for the whole list."""
    if not changeset_ids:
        return []
    ocdids = await changesets_db.jurisdictions_for_changesets(changeset_ids)
    published, rosters_and_values = await asyncio.gather(
        database.people.get_rosters_by_jurisdiction(list(set(ocdids.values()))),
        services_roster.proposed_rosters_and_source_values(changeset_ids),
    )
    rosters = {}
    overridden = {}
    for changeset_id, (roster, source_values) in rosters_and_values.items():
        rosters[changeset_id] = roster
        overridden[changeset_id] = source_values
    # What each scrape would actually change. `existing` and `proposed` are two rosters a
    # reader has to diff by eye; this is the diff.
    proposals = await proposals_for_requests(changeset_ids, rosters)
    existing_ids = [
        person["id"] for people in published.values() for person in people if person.get("id")
    ]
    summaries, organizations, assertions = await asyncio.gather(
        review_summaries(changeset_ids, published, rosters, proposals),
        posts_db.list_by_organization_for_jurisdictions(list(set(ocdids.values()))),
        assertions_for_people(existing_ids),
    )

    cards = []
    for changeset_id in changeset_ids:
        ocdid = ocdids.get(changeset_id)
        if ocdid is None:
            continue
        proposed = rosters.get(changeset_id, [])
        unique_source_urls = list(
            {url for person in proposed for url in (person.get("source_urls") or [])}
        )
        cards.append(
            ReviewCard(
                changeset_id=changeset_id,
                jurisdiction_ocdid=ocdid,
                existing=published.get(ocdid, []),
                proposed=proposed,
                changes=proposals.get(changeset_id, []),
                sources=[
                    ReviewSource(**source)
                    for source in build_sources(changeset_id, ocdid, unique_source_urls)
                ],
                overridden_source_values=overridden.get(changeset_id, {}),
                review=summaries.get(changeset_id, ReviewSummary()),
                organizations=organizations.get(ocdid, []),
                assertions={
                    person["id"]: assertions[person["id"]]
                    for person in published.get(ocdid, [])
                    if person.get("id") in assertions
                },
            )
        )
    return cards
