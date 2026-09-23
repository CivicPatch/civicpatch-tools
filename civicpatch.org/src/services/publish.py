"""Publishing a scrape: making its roster the live one.

The single entry point for "this data is now live", so there is one place to extend rather
than two paths to keep in step. Previously publishing was a side effect of the GitHub merge —
`publish_side_effects` re-read the merged file out of open-data to populate `people` — which
made the repo the authority for what is live and meant a dead merge worker meant stale data.
"""

import asyncio
import logging

import lib.buckets as buckets
import lib.storage as storage_service
from core.images import artifacts_key, promoted_key
from core.post_derivation import ChosenPost, DerivedPost, RosterEntry, derived_posts
from database import posts as posts_db
from database.database import get_pool
from database import source_records as source_records_db
from database.publications import (
    dismiss_changeset,
    publish_changeset,
)
from database.roles import get_roles
from schemas.activity import Change
from shared.schemas import RoleConfig
from shared.utils.statuses import DismissalReason
from shared.utils.taxonomy import build_taxonomy

logger = logging.getLogger(__name__)


async def promote_changeset_images(changeset_id: str) -> None:
    """Copy this changeset's photos from the artifacts bucket to the CDN.

    Only the copy: where a promoted photo *lives* is `core.images.published_image_url`, a pure
    function the fold applies, so nothing here rewrites a row.

    Runs at publish rather than submit so unreviewed photos never reach the CDN, mirroring
    the data itself: `local-unreviewed` is promoted to `local` by the same act of review.

    A photo that fails to copy is logged and skipped rather than failing the publish — the
    fold will still point at the CDN key, so the sweep is what should retry it (§19).

    Concurrent, because each copy is an independent round trip to object storage and this runs
    inside the publish request: nine councillors were nine serial copies, each also building
    its own boto client. `to_thread` rather than an async client because boto is synchronous —
    called directly these blocked the event loop, so they delayed every other request too, not
    only this one.
    """
    images = await source_records_db.changeset_images(changeset_id)
    if not images:
        return
    await asyncio.gather(*(asyncio.to_thread(_promote_image, image) for image in images))


def _promote_image(cdn_image: str) -> None:
    source_key = artifacts_key(cdn_image, buckets.ARTIFACTS)
    if not source_key:
        return
    dest_key = promoted_key(source_key)
    if not dest_key:
        logger.warning(f"Unexpected artifacts key, not promoting: {source_key}")
        return
    try:
        storage_service.copy_object(
            buckets.ARTIFACTS, source_key, buckets.CDN, dest_key
        )
    except Exception as e:
        logger.error(f"Failed to promote image {source_key}: {e}", exc_info=True)


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
            organization_id=rows[post_id]["organization_id"],
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


async def publish_roster(
    changeset_id: str,
    jurisdiction_ocdid: str,
    resolved_by_user_id: str | None = None,
    changes: Change | None = None,
) -> int:
    """Make a changeset live: promote its photos, then rebuild the roster from the facts.

    One call for every kind. A scrape and a hand edit differ in what facts they filed, not in
    how they publish, so there is no second entry point to keep in step.

    `changes`, when given, rides on the publish's own activity row — see `roster_edits.publish`.
    """
    await promote_changeset_images(changeset_id)
    written = await publish_changeset(
        changeset_id, jurisdiction_ocdid, resolved_by_user_id, changes
    )
    logger.info(f"[{changeset_id}] Published {written} people for {jurisdiction_ocdid}")
    return written


async def dismiss_people(
    changeset_id: str, resolved_by_user_id: str | None = None
) -> None:
    """Mark a scrape reviewed-and-not-published. Leaves the roster untouched."""
    # `dismiss_changeset` writes the dismiss_review log itself now, with the reason — so every
    # dismissal has one, not just the reviewer's. That is what retires `record_close`.
    await dismiss_changeset(changeset_id, DismissalReason.REJECTED, resolved_by_user_id)
    logger.info(f"[{changeset_id}] Dismissed without publishing")
