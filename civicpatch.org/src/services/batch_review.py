"""What a batch produced, for reviewing it in one pass.

Generic over batch kind: a sheet import and a state scrape both leave N unpublished requests,
and reviewing forty towns at once is the same job either way.

Each town comes back as counts only; its card is loaded per page through `/reviews/cards`.
"""

import asyncio
import logging

from database import changeset_batches, dismissals
from schemas.imports import (
    BatchReview,
    PublishResult,
    ReviewJurisdiction,
)
from services import publish
from core.changeset_lifecycle import ChangesetState
from core.roster_changes import ProposalCounts
from shared.utils.statuses import DismissalReason

logger = logging.getLogger(__name__)


async def batch_review(batch_id: str) -> BatchReview | None:
    """Every jurisdiction the batch made a request for, with its people and current state.

    Current state, not the state it was made in: since the run, a town may have been published
    or dismissed here, superseded by a newer roster, or expired.
    """
    batch, items = await asyncio.gather(
        changeset_batches.get(batch_id), changeset_batches.items(batch_id)
    )
    if batch is None:
        return None

    return BatchReview(
        batch_id=batch["id"],
        status=batch["status"],
        jurisdictions=[_reviewed(item) for item in items],
    )


def _reviewed(item: dict) -> ReviewJurisdiction:
    # Counted at import; None when that failed, which shows as unknown rather than wrong.
    counts = (
        ProposalCounts.model_validate(item["proposal_counts"])
        if item["proposal_counts"]
        else None
    )
    return ReviewJurisdiction(
        jurisdiction_ocdid=item["jurisdiction_ocdid"],
        name=item["name"] or item["jurisdiction_ocdid"],
        changeset_id=item["changeset_id"],
        changeset_state=item["changeset_state"],
        people=counts.people if counts else None,
        change_counts=counts.change_counts if counts else None,
    )


async def publish_selected(
    batch_id: str, changeset_ids: set[str], user_id: str
) -> list[PublishResult]:
    """Publish the towns a reviewer picked. Open-data picks them up in its 5-minute sweep.

    Sequential and isolated: publishing is a transaction per jurisdiction, and one refusing —
    the supersede guard turns down a roster older than one already live — must not cost the
    other thirty-nine theirs.

    Only open ones. A town decided since the page loaded — in another tab, or superseded — is
    left as it is.
    """
    items = await changeset_batches.items(batch_id)
    wanted = [
        item
        for item in items
        if item["changeset_id"] in changeset_ids
        and item["changeset_state"] == ChangesetState.OPEN
    ]

    results = []
    for item in wanted:
        try:
            await publish.publish_review(
                item["changeset_id"], item["jurisdiction_ocdid"], None, user_id
            )
        except Exception as e:
            logger.error(
                f"[{item['changeset_id']}] {item['jurisdiction_ocdid']}: publish failed: {e}",
                exc_info=True,
            )
            results.append(
                PublishResult(
                    changeset_id=item["changeset_id"],
                    jurisdiction_ocdid=item["jurisdiction_ocdid"],
                    published=False,
                    error=str(e),
                )
            )
            continue
        results.append(
            PublishResult(
                changeset_id=item["changeset_id"],
                jurisdiction_ocdid=item["jurisdiction_ocdid"],
                published=True,
            )
        )
    return results


async def dismiss_selected(
    batch_id: str, changeset_ids: set[str], user_id: str
) -> list[str]:
    """Reject the changesets a reviewer picked. Returns the ids dismissed — an open one in this
    batch only, since one decided since the page loaded is already decided."""
    items = await changeset_batches.items(batch_id)
    wanted = [
        item["changeset_id"]
        for item in items
        if item["changeset_id"] in changeset_ids
        and item["changeset_state"] == ChangesetState.OPEN
    ]
    return await dismissals.dismiss_all(wanted, DismissalReason.REJECTED, user_id)
