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
import lib.buckets as buckets
from core.image_promotion import artifacts_key, promoted_key, promoted_url
import services.change_logs as change_logs
from database.pipeline_runs import get_pipeline_run_data_json
from database.publications import dismiss_request, publish_request, record_open_data_url
from database.people import get_jurisdiction_people
from database.roles import get_roles
from core.post_derivation import DerivedPost, derived_posts
from shared.schemas import Official, RoleConfig
from shared.utils.taxonomy import build_taxonomy
from lib.temporal.types import CommitSource, OpenDataCommitRequest
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
        storage_service.copy_object(buckets.ARTIFACTS, source_key, buckets.CDN, dest_key)
    except Exception as e:
        logger.error(f"Failed to promote image {source_key}: {e}", exc_info=True)
        return person
    return {**person, "cdn_image": promoted_url(friendly_host, dest_key)}


async def _get_derived_posts(people: list[dict]) -> list[DerivedPost]:
    """Fetch the taxonomy, then derive what posts this roster implies.

    `get_` per the read verbs — it fetches and computes, writing nothing. That fetch is also
    the only reason this is async: `derived_posts` in `core` is pure and synchronous, and the
    await is `get_roles`. Never fatal: a roster that publishes without
    its posts is recoverable, since `source_records` still holds the evidence, but a roster
    that fails to publish because the taxonomy was unreachable is not.
    """
    try:
        roles = await get_roles()
        taxonomy = build_taxonomy(RoleConfig(roles=roles))
        return derived_posts([Official(**person) for person in people], taxonomy, roles)
    except Exception as e:
        logger.error(f"Failed to derive posts for publish: {e}", exc_info=True)
        return []


async def publish_people(
    request_id: str,
    jurisdiction_ocdid: str,
    people: list[dict],
    resolved_by_user_id: str | None = None,
) -> int:
    """Publish one scrape's roster. Returns the number of people written."""
    written = await publish_request(
        request_id,
        jurisdiction_ocdid,
        people,
        resolved_by_user_id,
        derived=await _get_derived_posts(people),
    )
    logger.info(
        f"[{request_id}] Published {written} people for {jurisdiction_ocdid}"
    )
    # Audited here rather than at the caller: publishing is this function, and the previous
    # home for this was the merge worker, which is going away.
    await change_logs.record_publish(request_id, resolved_by_user_id)
    return written


async def dismiss_people(request_id: str, resolved_by_user_id: str | None = None) -> None:
    """Mark a scrape reviewed-and-not-published. Leaves the roster untouched."""
    await dismiss_request(request_id, resolved_by_user_id)
    logger.info(f"[{request_id}] Dismissed without publishing")
    # ChangeLogType.CLOSE_REVIEW keeps its name: change_logs rows FK to change_log_types, so
    # the stored value cannot be renamed without orphaning history.
    await change_logs.record_close(request_id, resolved_by_user_id)


def unreviewed_file_path(jurisdiction_ocdid: str) -> str:
    folder = shared.utils.id_utils.unreviewed_folder(
        shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    )
    return f"data/{folder}.yml"


async def _render(source: CommitSource, request_id: str, jurisdiction_ocdid: str) -> list[dict]:
    if source is CommitSource.ROSTER:
        return await get_jurisdiction_people(jurisdiction_ocdid)
    return await get_pipeline_run_data_json(request_id) or []


async def commit_rendered_file(
    file_path: str,
    request_id: str,
    jurisdiction_ocdid: str,
    commit_message: str,
    source: CommitSource = CommitSource.SCRAPE,
) -> str | None:
    """Render a file out of the database and write it to open-data.

    The rendering happens here rather than at the caller so every retry produces current
    content: git holds a projection of the database, and a write that lands late should carry
    what is true when it lands, not what was true when it was queued.
    """
    roster = await _render(source, request_id, jurisdiction_ocdid)
    commit_url = await github_service.upsert_github_file(
        branch_name=github_service.DEFAULT_BRANCH,
        file_path=file_path,
        content_str=yaml_dump(roster),
        commit_message=commit_message,
    )
    if commit_url:
        await record_open_data_url(request_id, commit_url)
    return commit_url


def reviewed_file_path(jurisdiction_ocdid: str) -> str:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return f"data/{folder}.yml"


async def promote_to_reviewed(request_id: str, jurisdiction_ocdid: str) -> None:
    """Move a published jurisdiction from the unreviewed path to the canonical one.

    Queued rather than immediate, like every other open-data write: publishing is already a
    fact in the database by the time this runs. The reviewed file renders from `people`, not
    from this scrape — the canonical file is the jurisdiction's live roster, which can include
    people an earlier scrape published.
    """
    # avoid circular import: lib.temporal.workflows imports the activities module, which
    # imports this one, so importing the client at module scope closes the loop
    import lib.temporal.client as temporal_client

    await temporal_client.enqueue_open_data_commit(
        OpenDataCommitRequest(
            file_path=reviewed_file_path(jurisdiction_ocdid),
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            commit_message=f"Publish {jurisdiction_ocdid} ({request_id})",
            source=CommitSource.ROSTER,
            delete_path=unreviewed_file_path(jurisdiction_ocdid),
            delete_message=f"Promote {jurisdiction_ocdid} out of unreviewed ({request_id})",
        )
    )


async def commit_unreviewed_scrape(request_id: str, jurisdiction_ocdid: str) -> None:
    """Queue a scrape's commit to its unreviewed path on open-data `main`.

    Visible in the repo but not live: `classify_path` excludes the unreviewed level from the
    sync, so nothing here reaches `people`. Review is what promotes it to the reviewed path.

    Durable rather than immediate. The roster is already in the database, so the submit must
    not block on GitHub being slow, nor fail if it is down — Temporal retries until it lands.
    """
    # avoid circular import: lib.temporal.workflows imports the activities module, which
    # imports this one, so importing the client at module scope closes the loop
    import lib.temporal.client as temporal_client

    await temporal_client.enqueue_open_data_commit(
        OpenDataCommitRequest(
            file_path=unreviewed_file_path(jurisdiction_ocdid),
            request_id=request_id,
            jurisdiction_ocdid=jurisdiction_ocdid,
            commit_message=f"Unreviewed scrape: {jurisdiction_ocdid} ({request_id})",
        )
    )
