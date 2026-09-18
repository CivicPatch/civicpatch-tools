"""Publishing or dismissing a selection of review-pool cards at once.

The pool's counterpart to `batch_review`'s import actions. Each card goes through the same path
the single-card route takes, so a sheet import slipped into a selection is still refused, and the
reviewer is credited for each one decided.
"""

import logging

import database.review_session_entries as review_session_entries_db
from core.changeset_lifecycle import REVIEW_POOL_KINDS
from database import changesets as changesets_db
from database import dismissals
from schemas.imports import PublishResult
from services import roster_edits
from shared.utils.statuses import DismissalReason

logger = logging.getLogger(__name__)


async def publish_selected(changeset_ids: list[str], user_id: str) -> list[PublishResult]:
    """One at a time, each in its own transaction: one refusing must not cost the rest theirs."""
    ocdids = await changesets_db.jurisdictions_for_changesets(changeset_ids)
    results = []
    for changeset_id in changeset_ids:
        ocdid = ocdids.get(changeset_id, "")
        try:
            await roster_edits.publish_from_review(changeset_id, ocdid, None, user_id)
        except Exception as e:
            logger.error(f"[{changeset_id}] {ocdid}: publish failed: {e}", exc_info=True)
            results.append(
                PublishResult(
                    changeset_id=changeset_id,
                    jurisdiction_ocdid=ocdid,
                    published=False,
                    error=str(e),
                )
            )
            continue
        await review_session_entries_db.resolve_entries_for_changeset(changeset_id)
        results.append(
            PublishResult(changeset_id=changeset_id, jurisdiction_ocdid=ocdid, published=True)
        )
    return results


async def dismiss_selected(changeset_ids: list[str], user_id: str) -> list[str]:
    """Reject the selected cards. Returns the ids dismissed — open review-pool cards only."""
    kinds = await changesets_db.kinds_for_changesets(changeset_ids)
    in_pool = [
        changeset_id
        for changeset_id in changeset_ids
        if kinds.get(changeset_id) in REVIEW_POOL_KINDS
    ]
    dismissed = await dismissals.dismiss_all(in_pool, DismissalReason.REJECTED, user_id)
    for changeset_id in dismissed:
        await review_session_entries_db.resolve_entries_for_changeset(changeset_id)
    return dismissed
