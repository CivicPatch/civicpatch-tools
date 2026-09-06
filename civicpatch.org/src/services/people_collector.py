import logging

import environment
import lib.buckets as buckets
import lib.pipeline_artifacts as artifacts
import lib.storage as storage_service
from core.images import cdn_urls, records_with_images, resolve_images
from database.changesets import register_scrape_changeset
from database.issues import has_pending_issues, upsert_issue
from database.llm_calls import record_calls
from database.pipeline_runs import get_pipeline_run
from database.roles import get_roles
from database.source_records import insert_source_records
from schemas.pipeline_runs import (
    HandleSubmitPipelineRunArtifactsRequest,
    SubmitPipelineRunArtifactsResponse,
)
from services import roster_edits, roster_ingest
from services import pipeline_runs as pipeline_run_service
from services.jurisdiction_url import record_resolved_url, resolved_url
from services.review_proposal import review_summary_for_changeset
from shared.schemas import RoleConfig
from shared.utils.statuses import (
    RUN_LEVEL_ISSUE_TYPES,
    PipelineIssueType,
    PipelineRunStatus,
)
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
            f"[{request.pipeline_run_id}] Artifact submission failed: {e}", exc_info=True
        )
        # The same path the pipeline's own reports take; writing the row directly settled
        # nothing and told the open page nothing.
        await pipeline_run_service.apply_pipeline_run_status(
            request.pipeline_run_id,
            PipelineRunStatus.ERROR,
            None,
            request.jurisdiction_ocdid,
        )
        # Keyed on the proposal when there is one, so the issue resolves to a jurisdiction;
        # else on the run, which the issues page falls back to rendering.
        pipeline_run = await get_pipeline_run(request.pipeline_run_id)
        changeset_id = pipeline_run.get("changeset_id") if pipeline_run else None
        await upsert_issue(
            changeset_id or request.pipeline_run_id,
            PipelineIssueType.PIPELINE_ERROR,
            [{"error": str(e)}],
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
    changeset_id: str,
    jurisdiction_ocdid: str,
    records_by_person: dict[str, list[dict]],
) -> None:
    """Every sighting as the page gave it. Never fatal."""
    try:
        stored = await insert_source_records(
            changeset_id, jurisdiction_ocdid, records_by_person
        )
        logger.info(f"[{changeset_id}] Stored {stored} source record(s)")
    except Exception as e:
        logger.error(
            f"[{changeset_id}] Failed to store source records: {e}", exc_info=True
        )


async def _publish_if_nothing_to_review(
    changeset_id: str, jurisdiction_ocdid: str
) -> None:
    # The pipeline's own issues first: the summary below is derived from the two rosters and
    # cannot see them, so a run that stopped at its cost cap published its partial roster.
    if await has_pending_issues(changeset_id):
        return
    summary = await review_summary_for_changeset(changeset_id)
    if summary.get("issues"):
        return
    await roster_edits.publish(
        changeset_id, jurisdiction_ocdid, None, resolved_by_user_id=None
    )
    logger.info(f"[{changeset_id}] Published: nothing for a reviewer to look at")


async def _record_resolved_url(
    changeset_id: str, jurisdiction_ocdid: str, workflow_context: dict
) -> None:
    """Point the registry at wherever the scrape found the jurisdiction. Never fatal."""
    url = resolved_url(workflow_context)
    if not url:
        return
    try:
        await record_resolved_url(jurisdiction_ocdid, url)
    except Exception as e:
        logger.error(
            f"[{changeset_id}] Failed to record resolved URL: {e}", exc_info=True
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

    # Reconciliation classifies each sighting's label against this. Post derivation used to
    # read it here too and no longer does — `review_summary_for_changeset` builds its own, at the
    # point it needs one.
    taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))

    roster, records_by_person = await _reconcile_roster(
        request.jurisdiction_ocdid, data, workflow_context, taxonomy
    )
    source_urls, served = _image_url_maps(dirs.images, filenames_to_urls)
    updated_data, unserved = resolve_images(source_urls, served, roster)
    if unserved:
        logger.warning(f"No uploaded image for {', '.join(unserved)}")
    with open(data_file_path, "w") as f:
        f.write(yaml_dump(updated_data))

    # The run proposed a roster, so now there is something to review. Everything below is about
    # that proposal and takes its id; `request.pipeline_run_id` is the run's, and stays with the
    # attempt's evidence.
    changeset_id = await register_scrape_changeset(request.pipeline_run_id)

    await _store_source_records(
        changeset_id,
        request.jurisdiction_ocdid,
        records_with_images(records_by_person, source_urls, served),
    )
    # Before the publish decision, not after: these are what `_publish_if_nothing_to_review`
    # asks about, and filing them afterwards meant they never gated anything.
    for issue in workflow_context.get("data", {}).get("issues", []):
        await upsert_issue(changeset_id, issue["type"], [issue.get("data") or {}])

    await _apply_scrape_changes(changeset_id, request.jurisdiction_ocdid)
    await _record_resolved_url(
        changeset_id, request.jurisdiction_ocdid, workflow_context
    )


async def _apply_scrape_changes(changeset_id: str, jurisdiction_ocdid: str) -> None:
    """Settle the scrape if the reviewer would find nothing in it.

    All that is left of this at ingest. `advance_last_seen_at` and `close_absent` used to run
    here too, mutating *published* memberships on the strength of an *unreviewed* scrape. They
    were defended as observations — "the source stopped listing D" is true whether or not D
    left office — which holds for a good scrape and not for a bad one, and nothing here can
    tell which. The reviewer's own issue list can, which is what gates the publish below.

    It derives no posts of its own any more: `review_summary_for_changeset` derives what it needs
    from the proposed roster, at the point it is needed.

    Never fatal: a scrape whose people are stored must not error over its own bookkeeping. A
    failure leaves the changeset unresolved, which is the safe default — it awaits review.
    """
    try:
        await _publish_if_nothing_to_review(changeset_id, jurisdiction_ocdid)
    except Exception as e:
        logger.error(
            f"[{changeset_id}] Failed to apply the scrape's changes: {e}", exc_info=True
        )


async def _record_pipeline_error(pipeline_run_id: str, workflow_context: dict) -> None:
    """Keyed on the run: this branch is a scrape that never reached ingest, so it minted no
    proposal to hang the issue off."""
    context_data = workflow_context.get("data", {})
    reported = context_data.get("error_step")
    detail = context_data.get("error_detail") or {}

    if reported and reported not in RUN_LEVEL_ISSUE_TYPES:
        logger.warning(
            f"[{pipeline_run_id}] Unrecognised error_step {reported!r}; filing as "
            f"{PipelineIssueType.PIPELINE_ERROR}"
        )
        detail = {**detail, "reported_error_step": reported}
        reported = None

    await upsert_issue(
        pipeline_run_id, reported or PipelineIssueType.PIPELINE_ERROR, [detail]
    )


async def _handle_submit_pipeline_run_artifacts(
    request: HandleSubmitPipelineRunArtifactsRequest,
) -> SubmitPipelineRunArtifactsResponse:
    dirs = await artifacts.unpack(request.zip_path, request.temp_dir)

    filenames_to_urls = await storage_service.upload_directory(
        PUBLIC_BUCKET, dirs.images, request.pipeline_run_id
    )
    await storage_service.upload_directory(
        PRIVATE_BUCKET, dirs.debug, request.pipeline_run_id
    )

    # Best-effort, like the Sheets push it replaces: an unrecorded cost must not fail a submit
    # whose people are already stored.
    try:
        recorded = await record_calls(
            request.pipeline_run_id, artifacts.read_costs(dirs.debug)["llm_costs"]
        )
        logger.info(f"[{request.pipeline_run_id}] Recorded {recorded} LLM call(s)")
    except Exception as e:
        logger.error(
            f"Failed to record LLM calls for {request.pipeline_run_id}: {e}", exc_info=True
        )

    workflow_context = artifacts.read_workflow_context(dirs.debug)

    if request.pipeline_run_status == PipelineRunStatus.SUCCESS:
        await _ingest_roster(request, dirs, filenames_to_urls, workflow_context)
    else:
        await _record_pipeline_error(request.pipeline_run_id, workflow_context)

    return SubmitPipelineRunArtifactsResponse(
        status="uploaded",
        pipeline_run_id=request.pipeline_run_id,
        jurisdiction_ocdid=request.jurisdiction_ocdid,
    )
