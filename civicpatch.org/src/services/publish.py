"""Publishing a scrape: making its roster the live one.

The single entry point for "this data is now live", so there is one place to extend rather
than two paths to keep in step. Previously publishing was a side effect of the GitHub merge —
`publish_side_effects` re-read the merged file out of open-data to populate `people` — which
made the repo the authority for what is live and meant a dead merge worker meant stale data.
"""

import logging

import environment
import lib.buckets as buckets
import lib.github.api as github_service
import lib.github.git_data as git_data
import lib.storage as storage_service
import shared.utils.id_utils
from core.images import artifacts_key, promoted_key, promoted_url
from core.output_hash import hash_text
from core.membership_label import derive_post_label
from core.post_derivation import ChosenPost, DerivedPost, RosterEntry, derived_posts
from database import output_hashes as output_hashes_db
from database import posts as posts_db
from database.database import get_pool
from database.people import get_roster
from database.publications import dismiss_request, publish_request, record_change_url
from database.roles import get_roles
from lib.temporal.types import (
    OpenDataBatchCommitRequest,
    OpenDataCommitItem,
)
from shared.schemas import DerivedPerson, OpenStatesPersonRecord, RoleConfig
from shared.utils.people_utils import person_sort_key
from shared.utils.statuses import DismissalReason
from shared.utils.taxonomy import Taxonomy, build_taxonomy
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
    source_key = artifacts_key(cdn_image, buckets.ARTIFACTS)
    if not source_key:
        return person
    dest_key = promoted_key(source_key)
    if not dest_key:
        logger.warning(f"Unexpected artifacts key, not promoting: {source_key}")
        return person
    try:
        storage_service.copy_object(
            buckets.ARTIFACTS, source_key, buckets.CDN, dest_key
        )
    except Exception as e:
        logger.error(f"Failed to promote image {source_key}: {e}", exc_info=True)
        return person
    return {**person, "cdn_image": promoted_url(friendly_host, dest_key)}


def picks_in(roster: list[RosterEntry]) -> dict[str, str]:
    """The post each person was picked for, by person id."""
    return {record.id: record.post_id for record in roster if record.id and record.post_id}


async def chosen_posts(picks: dict[str, str]) -> dict[str, ChosenPost]:
    """The seat a reviewer picked, **by person id**.

    Keyed on the person so the derivation's input can be purely what the source said: a pick is
    a human's answer and travels here instead of riding on the record.

    A pick naming a post that no longer exists is simply absent, and the derivation falls back
    to the labels rather than losing the person.
    """
    if not picks:
        return {}
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts_db.identities_by_id(cur, list(set(picks.values())))
    return {
        person_id: ChosenPost(
            role_id=rows[post_id]["role_id"],
            division_ocdid=rows[post_id]["division_ocdid"],
        )
        for person_id, post_id in picks.items()
        if post_id in rows
    }


async def _get_derived_posts(people: list[dict]) -> list[DerivedPost]:
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))
    roster = [RosterEntry(**person) for person in people]
    return derived_posts(roster, taxonomy, roles, await chosen_posts(picks_in(roster)))


async def publish_people(
    changeset_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str | None = None,
) -> int:
    """Publish one scrape's roster. Returns the number of people written."""
    written = await publish_request(
        changeset_id,
        jurisdiction_ocdid,
        people,
        resolved_by_user_id,
        derived=await _get_derived_posts(people),
    )
    logger.info(f"[{changeset_id}] Published {written} people for {jurisdiction_ocdid}")
    return written


async def dismiss_people(
    changeset_id: str, resolved_by_user_id: str | None = None
) -> None:
    """Mark a scrape reviewed-and-not-published. Leaves the roster untouched."""
    # `dismiss_request` writes the dismiss_review log itself now, with the reason — so every
    # dismissal has one, not just the reviewer's. That is what retires `record_close`.
    await dismiss_request(changeset_id, DismissalReason.REJECTED, resolved_by_user_id)
    logger.info(f"[{changeset_id}] Dismissed without publishing")
