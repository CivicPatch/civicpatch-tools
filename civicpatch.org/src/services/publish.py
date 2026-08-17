"""Publishing a scrape: making its roster the live one.

The single entry point for "this data is now live", so there is one place to extend rather
than two paths to keep in step. Previously publishing was a side effect of the GitHub merge —
`publish_side_effects` re-read the merged file out of open-data to populate `people` — which
made the repo the authority for what is live and meant a dead merge worker meant stale data.
"""

import logging

import environment
import lib.github.api as github_service
import lib.storage as storage_service
import shared.utils.id_utils
from core.image_promotion import (
    ARTIFACTS_BUCKET,
    CDN_BUCKET,
    artifacts_key,
    promoted_key,
    promoted_url,
)
from database.publications import publish_request
from shared.utils.yaml_utils import yaml_dump

logger = logging.getLogger(__name__)


def promote_images(people: list[dict]) -> list[dict]:
    """Move this roster's photos from the artifacts bucket to the CDN, and point the records
    at their new home. Mutates nothing the caller owns — returns the rewritten roster.

    Runs at publish rather than submit so unreviewed photos never reach the CDN, mirroring
    the data itself: `local-unreviewed` is promoted to `local` by the same act of review.

    A photo that fails to copy is left pointing at the artifacts bucket rather than failing
    the publish — the URL still resolves, it is just not on the permanent host yet.
    """
    friendly_host = environment.get_env_vars()["FRIENDLY_STORAGE_HOST"]
    promoted = []
    for person in people:
        promoted.append(_promote_person_image(person, friendly_host))
    return promoted


def _promote_person_image(person: dict, friendly_host: str) -> dict:
    cdn_image = person.get("cdn_image")
    if not cdn_image:
        return person
    source_key = artifacts_key(cdn_image)
    if not source_key:
        return person
    dest_key = promoted_key(source_key)
    if not dest_key:
        logger.warning(f"Unexpected artifacts key, not promoting: {source_key}")
        return person
    try:
        storage_service.copy_object(ARTIFACTS_BUCKET, source_key, CDN_BUCKET, dest_key)
    except Exception as e:
        logger.error(f"Failed to promote image {source_key}: {e}", exc_info=True)
        return person
    return {**person, "cdn_image": promoted_url(friendly_host, dest_key)}


async def publish_people(
    request_id: str, jurisdiction_ocdid: str, people: list[dict]
) -> int:
    """Publish one scrape's roster. Returns the number of people written."""
    written = await publish_request(request_id, jurisdiction_ocdid, people)
    logger.info(
        f"[{request_id}] Published {written} people for {jurisdiction_ocdid}"
    )
    return written


def unreviewed_file_path(jurisdiction_ocdid: str) -> str:
    folder = shared.utils.id_utils.unreviewed_folder(
        shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    )
    return f"data/{folder}.yml"


async def commit_unreviewed_scrape(
    request_id: str, jurisdiction_ocdid: str, people: list[dict]
) -> bool:
    """Commit a scrape to its unreviewed path on open-data `main`, before anyone has read it.

    Visible in the repo but not live: `classify_path` excludes the unreviewed level from the
    sync, so nothing here reaches `people`. Review is what promotes it to the reviewed path.

    Returns False rather than raising — the roster is already stored in the database by the
    time this runs, so a failed copy must not fail the submit.
    """
    return await github_service.upsert_github_file(
        branch_name=github_service.DEFAULT_BRANCH,
        file_path=unreviewed_file_path(jurisdiction_ocdid),
        content_str=yaml_dump(people),
        commit_message=f"Unreviewed scrape: {jurisdiction_ocdid} ({request_id})",
    )
