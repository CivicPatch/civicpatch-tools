"""Making a reviewed scrape's roster live.

A reviewer's edits are filed as claims by `services/jurisdiction_edits.py::edit_in_review`, not
here. By the time `publish` runs they are already facts, so the roster to publish is simply the
one the facts derive.
"""

from typing import List

from core.changeset_lifecycle import REVIEW_POOL_KINDS
from database.changesets import get_changeset_kind
from schemas.activity import Change
from services.publish import publish_roster
from services.roster import proposed_roster

class MissingRoster(Exception):
    """The scrape has no recorded roster, so there is nothing to edit or publish."""


class NotInReviewPool(Exception):
    """A sheet import is not bulk-published from the queue."""


async def publish_from_review(
    changeset_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str,
) -> None:
    """`publish`, for bulk review — which offers only the kinds the review pool does."""
    kind = await get_changeset_kind(changeset_id)
    if kind is None:
        raise MissingRoster(changeset_id)
    if kind not in REVIEW_POOL_KINDS:
        raise NotInReviewPool(changeset_id)
    await publish(changeset_id, jurisdiction_ocdid, edited, resolved_by_user_id)


async def publish(
    changeset_id: str,
    jurisdiction_ocdid: str,
    edited: List[dict] | None,
    resolved_by_user_id: str | None,
    changes: Change | None = None,
) -> None:
    """Make this scrape's roster live.

    Nothing here commits: `WriteRecentChangesWorkflow` mirrors to open-data and the sheets from
    `activity`. The old `publish` / `publish_to_database` split named a choice that
    disappeared when mirroring moved to the sweep, and left the two identical.

    `changes`, when given, rides on the publish's own activity row instead of a separate one —
    see `edit_published`, the only caller that passes it.
    """
    roster = edited
    if roster is None:
        # `proposed_roster`, not `scraped_roster`: publishing without editing still has to
        # carry what a human stated on an earlier visit.
        roster = await proposed_roster(changeset_id, jurisdiction_ocdid)
    # Publishing an empty roster retires every person in the jurisdiction. That was unreachable
    # while the review pool required an open PR; the request is the only record now.
    if not roster:
        raise MissingRoster(changeset_id)
    # Photos promote with the data: publishing is what moves them off the artifacts bucket.
    await publish_roster(changeset_id, jurisdiction_ocdid, resolved_by_user_id, changes)
