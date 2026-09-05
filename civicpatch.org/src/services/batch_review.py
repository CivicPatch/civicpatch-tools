"""What a batch produced, for reviewing it in one pass.

Generic over batch kind: a sheet import and a state scrape both leave N unpublished requests,
and reviewing forty towns at once is the same job either way.

The people come back as a limited view — name, photo, seat. That is what makes forty towns
scannable where a field-by-field diff is not, and it is a *scan*: the full card is still one
click away for anything that looks wrong.
"""

import asyncio
import logging

from database import changeset_batches
from schemas.imports import (
    BatchReview,
    PublishResult,
    ReviewJurisdiction,
    ReviewPerson,
)
from services import roster_edits
from services.sinks.open_data import promote_batch_to_reviewed
from services.roster import proposed_rosters
from shared.utils.statuses import RequestReviewStatus

logger = logging.getLogger(__name__)


def _person(person: dict) -> ReviewPerson:
    return ReviewPerson(
        id=person.get("id", ""),
        name=person.get("name", ""),
        label=person.get("label") or "",
        image=person.get("cdn_image") or person.get("image"),
        urls=person.get("urls") or [],
        phones=person.get("phones") or [],
        emails=person.get("emails") or [],
        start_date=person.get("start_date"),
        end_date=person.get("end_date"),
        role_id=person.get("role_id"),
        unmatched_text=person.get("unmatched_text") or [],
    )


async def batch_review(batch_id: str) -> BatchReview | None:
    """Every jurisdiction the batch made a request for, with its people and current state.

    Current state, not the state it was made in: between the run and somebody opening this, a
    card may have been published or dismissed from the ordinary review queue — an import's
    requests are ordinary review cards, not a private set.
    """
    batch, items = await asyncio.gather(
        changeset_batches.get(batch_id), changeset_batches.items(batch_id)
    )
    if batch is None:
        return None

    # Every card, published or not. This is what *this import* proposed, derived from its own
    # sightings — which outlive publishing. Reading only the pending ones left a published
    # locality claiming "0 people", and reading the jurisdiction's live roster instead would
    # answer a different question: who is seated there now, including people no scrape in this
    # batch ever saw.
    rosters = await proposed_rosters([item["changeset_id"] for item in items])

    return BatchReview(
        batch_id=batch["id"],
        status=batch["status"],
        jurisdictions=[
            ReviewJurisdiction(
                jurisdiction_ocdid=item["jurisdiction_ocdid"],
                name=item["name"] or item["jurisdiction_ocdid"],
                changeset_id=item["changeset_id"],
                review_status=item["review_status"],
                people=[
                    _person(person)
                    for person in rosters.get(item["changeset_id"], [])
                ],
            )
            for item in items
        ],
    )


async def publish_selected(
    batch_id: str, jurisdiction_ocdids: set[str], user_id: str
) -> list[PublishResult]:
    """Publish the towns a reviewer picked, then mirror them all in one open-data commit.

    Sequential and isolated: publishing is a transaction per jurisdiction, and one refusing —
    the supersede guard turns down a roster older than one already live — must not cost the
    other thirty-nine theirs. The commit comes after, covering whichever ones got through,
    because the reviewer published once and open-data should say so once.

    Only pending ones. A town published from the ordinary queue since the page loaded is
    already live, and re-publishing it would supersede itself for nothing.
    """
    items = await changeset_batches.items(batch_id)
    wanted = [
        item
        for item in items
        if item["jurisdiction_ocdid"] in jurisdiction_ocdids
        and item["review_status"] == RequestReviewStatus.PENDING
    ]

    results = []
    published: dict[str, str] = {}
    for item in wanted:
        try:
            await roster_edits.publish(
                item["changeset_id"], item["jurisdiction_ocdid"], None, user_id
            )
        except Exception as e:
            logger.error(
                f"[{item['changeset_id']}] {item['jurisdiction_ocdid']}: publish failed: {e}",
                exc_info=True,
            )
            results.append(
                PublishResult(
                    jurisdiction_ocdid=item["jurisdiction_ocdid"],
                    published=False,
                    error=str(e),
                )
            )
            continue
        published[item["changeset_id"]] = item["jurisdiction_ocdid"]
        results.append(
            PublishResult(
                jurisdiction_ocdid=item["jurisdiction_ocdid"], published=True
            )
        )

    # Queued, so a slow or failed GitHub write cannot affect publishes that already committed.
    await promote_batch_to_reviewed(batch_id, published)
    return results
