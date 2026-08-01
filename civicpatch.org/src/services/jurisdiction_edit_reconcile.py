"""Close out manual jurisdiction edits whose values are already live.

The PR is the mechanism, not the fact. What we actually want to know is whether the
edit landed — and the projection already answers that, for free, however it landed:
merged by us, squashed by a maintainer, or applied by someone else entirely.

Runs at the tail of whichever workflow projects jurisdiction data, so it reads a
tree that was refreshed moments earlier. It only ever concludes *yes*: a value that
has not appeared may be pending or may have been rejected, and those are not
distinguishable from here.
"""

import logging

import core.jurisdiction_patch as jurisdiction_patch
import database.requests as requests_db
from services.pull_request_sync import apply_pull_request_status
from shared.utils.statuses import PullRequestStatus

logger = logging.getLogger(__name__)


async def reconcile_landed_jurisdiction_edits() -> int:
    """Returns how many edits were found to have landed."""
    pending = await requests_db.get_open_jurisdiction_edits()
    landed = 0
    for edit in pending:
        if not jurisdiction_patch.patch_is_live(edit["patch"], edit["current"]):
            continue
        await apply_pull_request_status(edit["request_id"], PullRequestStatus.MERGED)
        landed += 1

    if landed:
        logger.info("reconcile: %d jurisdiction edit(s) are live; marked merged", landed)
    return landed
