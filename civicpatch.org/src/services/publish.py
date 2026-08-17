"""Publishing a scrape: making its roster the live one.

The single entry point for "this data is now live", so there is one place to extend rather
than two paths to keep in step. Previously publishing was a side effect of the GitHub merge —
`publish_side_effects` re-read the merged file out of open-data to populate `people` — which
made the repo the authority for what is live and meant a dead merge worker meant stale data.
"""

import logging

from database.publications import publish_request

logger = logging.getLogger(__name__)


async def publish_people(
    request_id: str, jurisdiction_ocdid: str, people: list[dict]
) -> int:
    """Publish one scrape's roster. Returns the number of people written."""
    written = await publish_request(request_id, jurisdiction_ocdid, people)
    logger.info(
        f"[{request_id}] Published {written} people for {jurisdiction_ocdid}"
    )
    return written
