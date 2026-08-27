import logging

import environment
import lib.buckets as buckets
import lib.pipeline_artifacts as artifacts
import lib.storage as storage_service
from core.images import cdn_urls, records_with_images, resolve_images
from core.membership_proposal import (
    ExistingMembership,
    ProposedChange,
    nothing_to_review,
    propose,
)
from core.post_derivation import DerivedPost
from database import memberships as memberships_db
from database import requests as requests_db
from database.database import get_pool
from database.issues import upsert_issue
from database.pipeline_runs import (
    update_pipeline_run_status,
)
from database.roles import get_roles
from database.source_records import insert_source_records
from schemas.pipeline_runs import (
    HandleSubmitPipelineRunArtifactsRequest,
    SubmitPipelineRunArtifactsResponse,
)
from services import pipeline_costs, roster_ingest
from services.jurisdiction_url import record_resolved_url, resolved_url
from shared.schemas import Person, Role, RoleConfig
from shared.utils.statuses import PipelineIssueType, PipelineRunStatus
from shared.utils.taxonomy import Taxonomy, build_taxonomy
from shared.utils.yaml_utils import yaml_dump, yaml_load

PUBLIC_BUCKET = buckets.ARTIFACTS
PRIVATE_BUCKET = buckets.DEBUG

INSTANCE_DOMAIN = "civicpatch.org"  # Just hardcode it for now...

# The value `people.status` is checked against; the column's CHECK constraint is the guard.

logger = logging.getLogger(__name__)


async def handle_submit_pipeline_run_artifacts(
    request: HandleSubmitPipelineRunArtifactsRequest,
) -> SubmitPipelineRunArtifactsResponse:
    try:
        return await _handle_submit_pipeline_run_artifacts(request)
    except Exception as e:
        logger.error(
            f"[{request.request_id}] Artifact submission failed: {e}", exc_info=True
        )
        await update_pipeline_run_status(
            request.request_id, status=PipelineRunStatus.ERROR, progress=None
        )
        await upsert_issue(
            request.request_id, PipelineIssueType.PIPELINE_ERROR, [{"error": str(e)}]
        )
        raise


async def _identities(jurisdiction_ocdid: str, workflow_context: dict) -> dict:
    """The prior reconciliation groups against: our own published people, else the scrape's
    research for a jurisdiction we have never published. That fallback is the pipeline's own —
    a curated sheet has no research step, which is why `reconcile_roster` takes this as an
    argument rather than deriving it."""
    published = await roster_ingest.published_identities(jurisdiction_ocdid)
    if published:
        return published
    research = workflow_context.get("data", {}).get("research_municipality_step") or {}
    return research.get("identities") or {}


async def _reconcile_roster(
    jurisdiction_ocdid: str,
    rows: list[dict],
    workflow_context: dict,
    taxonomy: Taxonomy,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """The roster this submit means.

    Fatal on failure, unlike the writes below: everything downstream consumes it.
    """
    identities = await _identities(jurisdiction_ocdid, workflow_context)
    return await roster_ingest.reconcile_roster(
        jurisdiction_ocdid, rows, identities, taxonomy
    )


def _image_url_maps(image_file_dir: str, filenames_to_urls: dict) -> tuple[dict, dict]:
    """The impure edge of image resolution: an env read and a file read. The mapping itself is
    `core.images.cdn_urls`."""
    env = environment.get_env_vars()
    return artifacts.read_image_map(image_file_dir), cdn_urls(
        filenames_to_urls, env["STORAGE_ENDPOINT"], PUBLIC_BUCKET, INSTANCE_DOMAIN
    )


async def _store_source_records(
    request_id: str,
    jurisdiction_ocdid: str,
    records_by_person: dict[str, list[dict]],
) -> None:
    """Every sighting as the page gave it. Never fatal."""
    try:
        stored = await insert_source_records(
            request_id, jurisdiction_ocdid, records_by_person
        )
        logger.info(f"[{request_id}] Stored {stored} source record(s)")
    except Exception as e:
        logger.error(
            f"[{request_id}] Failed to store source records: {e}", exc_info=True
        )


async def _get_proposed_changes(
    cur, jurisdiction_ocdid: str, derived: list[DerivedPost]
) -> list[ProposedChange]:
    """What this scrape would change about who holds what. Read once, used by both steps below."""
    held = (await memberships_db.open_by_jurisdiction(cur, [jurisdiction_ocdid]))[
        jurisdiction_ocdid
    ]
    return propose(derived, [ExistingMembership(**row) for row in held])


async def _dismiss_if_nothing_to_review(
    cur, request_id: str, changes: list[ProposedChange]
) -> None:
    """Retire a scrape nothing needs to be asked about.

    Guarded in its own statement, so losing a race to a reviewer publishing leaves their
    decision alone.
    """
    if not nothing_to_review(changes):
        return
    if await requests_db.dismiss_as_unchanged(cur, request_id):
        logger.info(f"[{request_id}] Dismissed: nothing to review")


async def _find_or_create_posts(
    request_id: str,
    jurisdiction_ocdid: str,
    records: list[dict],
    roles: list[Role],
    taxonomy: Taxonomy,
) -> list:
    """Derive the posts this scrape implies and write them, so review has real posts to
    point a person at.

    Never fatal: a scrape whose people are stored must not error over its own bookkeeping, and
    posts are re-derivable from the sightings.
    """
    try:
        derived = await roster_ingest.derive_and_store_posts(
            request_id, jurisdiction_ocdid, records, roles, taxonomy
        )
        logger.info(f"[{request_id}] Derived {len(derived)} post(s)")
        return derived
    except Exception as e:
        logger.error(f"[{request_id}] Failed to derive posts: {e}", exc_info=True)
        return []


async def _record_resolved_url(
    request_id: str, jurisdiction_ocdid: str, workflow_context: dict
) -> None:
    """Point the registry at wherever the scrape found the jurisdiction. Never fatal."""
    url = resolved_url(workflow_context)
    if not url:
        return
    try:
        await record_resolved_url(jurisdiction_ocdid, url)
    except Exception as e:
        logger.error(
            f"[{request_id}] Failed to record resolved URL: {e}", exc_info=True
        )


async def _ingest_roster(
    request: HandleSubmitPipelineRunArtifactsRequest,
    dirs: artifacts.ArtifactDirs,
    filenames_to_urls: dict,
    workflow_context: dict,
) -> None:
    """Reconcile the scrape into people, and derive everything that follows from them."""
    if not await artifacts.has_expected_output(dirs.output):
        raise Exception(
            f"Uploaded zip file is missing expected files matching patterns: {artifacts.OUTPUT_PATTERNS}"
        )

    data_file_path = artifacts.find_roster_file(dirs.output)
    with open(data_file_path, "r") as f:
        data = yaml_load(f.read())

    # Read once and threaded down: every step below classifies against it, and a roles edit
    # landing mid-submit would otherwise leave them disagreeing about the same scrape.
    roles = await get_roles()
    taxonomy = build_taxonomy(RoleConfig(roles=roles))

    roster, records_by_person = await _reconcile_roster(
        request.jurisdiction_ocdid, data, workflow_context, taxonomy
    )
    source_urls, served = _image_url_maps(dirs.images, filenames_to_urls)
    updated_data, unserved = resolve_images(source_urls, served, roster)
    if unserved:
        logger.warning(f"No uploaded image for {', '.join(unserved)}")
    with open(data_file_path, "w") as f:
        f.write(yaml_dump(updated_data))

    await _store_source_records(
        request.request_id,
        request.jurisdiction_ocdid,
        records_with_images(records_by_person, source_urls, served),
    )
    derived = await _find_or_create_posts(
        request.request_id, request.jurisdiction_ocdid, updated_data, roles, taxonomy
    )
    await _apply_scrape_changes(request.request_id, request.jurisdiction_ocdid, derived)
    await _record_resolved_url(
        request.request_id, request.jurisdiction_ocdid, workflow_context
    )


    for issue in workflow_context.get("data", {}).get("issues", []):
        await upsert_issue(request.request_id, issue["type"], [issue.get("data") or {}])


async def _apply_scrape_changes(
    request_id: str, jurisdiction_ocdid: str, derived: list[DerivedPost]
) -> None:
    """Retire the scrape if it proposes nothing anyone needs to look at.

    All that is left of this at ingest. `advance_last_seen_at` and `close_absent` used to run
    here too, mutating *published* memberships on the strength of an *unreviewed* scrape. They
    were defended as observations — "the source stopped listing D" is true whether or not D
    left office — which holds for a good scrape and not for a bad one, and nothing here can
    tell which. `publish_request` already does both, so this was a duplicate that ran too
    early.

    Never fatal, like the other derived writes: a scrape whose people are stored must not error
    over its own bookkeeping.
    """
    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            changes = await _get_proposed_changes(cur, jurisdiction_ocdid, derived)
            await _dismiss_if_nothing_to_review(cur, request_id, changes)
            await conn.commit()
    except Exception as e:
        logger.error(
            f"[{request_id}] Failed to apply the scrape's changes: {e}", exc_info=True
        )


async def _record_pipeline_error(request_id: str, workflow_context: dict) -> None:
    context_data = workflow_context.get("data", {})
    error_step = context_data.get("error_step") or PipelineIssueType.PIPELINE_ERROR
    await upsert_issue(request_id, error_step, [context_data.get("error_detail") or {}])


async def _handle_submit_pipeline_run_artifacts(
    request: HandleSubmitPipelineRunArtifactsRequest,
) -> SubmitPipelineRunArtifactsResponse:
    dirs = await artifacts.unpack(request.zip_path, request.temp_dir)

    filenames_to_urls = await storage_service.upload_directory(
        PUBLIC_BUCKET, dirs.images, request.request_id
    )
    await storage_service.upload_directory(
        PRIVATE_BUCKET, dirs.debug, request.request_id
    )

    try:
        await pipeline_costs.send_costs(dirs.debug)
    except Exception as e:
        logger.error(
            f"Failed to send costs for {request.request_id}: {e}", exc_info=True
        )

    workflow_context = artifacts.read_workflow_context(dirs.debug)

    if request.pipeline_run_status == PipelineRunStatus.SUCCESS:
        await _ingest_roster(request, dirs, filenames_to_urls, workflow_context)
    else:
        await _record_pipeline_error(request.request_id, workflow_context)

    return SubmitPipelineRunArtifactsResponse(
        status="uploaded",
        request_id=request.request_id,
        jurisdiction_ocdid=request.jurisdiction_ocdid,
    )
