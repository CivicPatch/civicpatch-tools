import logging

import environment
import lib.buckets as buckets
import lib.pipeline_artifacts as artifacts
import lib.storage as storage_service
from core.ingest_people import (
    cdn_urls,
    identified,
    images_by_person,
    officials_from_rows,
    records_by_person,
    resolve_images,
)
from core.membership_proposal import (
    ExistingMembership,
    ProposedChange,
    nothing_to_review,
    propose,
    still_held,
    still_listed,
)
from core.post_derivation import DerivedPost, derived_posts
from database import memberships as memberships_db
from database import posts as posts_db
from database import requests as requests_db
from database.database import get_pool
from database.issues import upsert_issue
from database.people import get_people_for_jurisdiction
from database.pipeline_runs import (
    run_updated_at,
    update_pipeline_run_data,
    update_pipeline_run_review_json,
    update_pipeline_run_status,
)
from database.roles import get_roles
from database.source_records import insert_source_records
from schemas.pipeline_runs import (
    HandleSubmitPipelineRunArtifactsRequest,
    SubmitPipelineRunArtifactsResponse,
)
from services import pipeline_costs
from services.jurisdiction_url import record_resolved_url, resolved_url
from services.publish import chosen_posts
from shared.schemas import Person, Role, RoleConfig
from shared.utils.config_utils import get_unique_roles
from shared.utils.name_utils import person_list_to_identities
from shared.utils.person_id_utils import resolve_people_ids
from shared.utils.review_utils import ReviewInputs, build_review_summary
from shared.utils.statuses import PipelineIssueType, PipelineRunStatus
from shared.utils.taxonomy import Taxonomy, build_taxonomy
from shared.utils.yaml_utils import yaml_dump, yaml_load

PUBLIC_BUCKET = buckets.ARTIFACTS
PRIVATE_BUCKET = buckets.DEBUG

INSTANCE_DOMAIN = "civicpatch.org"  # Just hardcode it for now...

# The value `people.status` is checked against; the column's CHECK constraint is the guard.
ACTIVE_PERSON_STATUS = "active"

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
    research for a jurisdiction we have never published."""
    existing = await get_people_for_jurisdiction(
        jurisdiction_ocdid, status=ACTIVE_PERSON_STATUS
    )
    if existing:
        return person_list_to_identities(existing)
    research = workflow_context.get("data", {}).get("research_municipality_step") or {}
    return research.get("identities") or {}


async def _reconcile_roster(
    jurisdiction_ocdid: str,
    rows: list[dict],
    workflow_context: dict,
    taxonomy: Taxonomy,
) -> tuple[list[dict], dict[str, list[dict]]]:
    """The roster this submit means, whichever shape it arrived in.

    Fatal on failure, unlike the writes below: everything downstream consumes it.
    """
    identities = await _identities(jurisdiction_ocdid, workflow_context)
    roster, records_by_name = officials_from_rows(
        rows, identities, taxonomy, jurisdiction_ocdid, logger
    )
    identified_roster = await _assign_ids(jurisdiction_ocdid, roster)
    return identified_roster, records_by_person(identified_roster, records_by_name)


async def _assign_ids(jurisdiction_ocdid: str, roster: list[dict]) -> list[dict]:
    """Give every person the id we already know them by, or a fresh one.

    Everyone, not only the entries arriving without one: `resolve_people_ids` guards against
    two entries claiming one person, and only sees the collision if it sees both. Matched
    against inactive people too, so someone returning after a term away keeps their id.
    """
    everyone = await get_people_for_jurisdiction(jurisdiction_ocdid)
    resolutions = resolve_people_ids(
        roster, everyone, person_list_to_identities(everyone)
    )
    return [
        identified(person, resolution)
        for person, resolution in zip(roster, resolutions)
    ]


async def _review_summary(
    roster: list[dict], workflow_context: dict, roles: list[Role]
) -> dict:
    """The issues a reviewer sees.

    Runs after reconciliation because every check counts people. Compared against the research
    step's identities, not ours: "absent" means this run did not find who it set out to.

    Never fatal — the people are already stored by now.
    """
    try:
        return await _build_review_summary(roster, workflow_context, roles)
    except Exception as e:
        logger.error(f"Failed to build review summary: {e}", exc_info=True)
        return {}


async def _build_review_summary(
    roster: list[dict], workflow_context: dict, roles: list[Role]
) -> dict:
    research = workflow_context.get("data", {}).get("research_municipality_step") or {}
    identities = research.get("identities") or {}
    summary = build_review_summary(
        [{"name": name} for name in identities],
        roster,
        ReviewInputs(
            identities=identities,
            unique_roles=get_unique_roles(RoleConfig(roles=roles)),
        ),
        research.get("origin_source") or "google_gemini",
    )
    # `Issue` is a model and this goes to `json.dumps`.
    return {**summary, "issues": [issue.model_dump() for issue in summary["issues"]]}


def _image_url_maps(image_file_dir: str, filenames_to_urls: dict) -> tuple[dict, dict]:
    """The impure edge of image resolution: an env read and a file read. The mapping itself is
    `core.ingest_people.cdn_urls`."""
    env = environment.get_env_vars()
    return artifacts.read_image_map(image_file_dir), cdn_urls(
        filenames_to_urls, env["STORAGE_ENDPOINT"], PUBLIC_BUCKET, INSTANCE_DOMAIN
    )


async def _store_source_records(
    request_id: str,
    jurisdiction_ocdid: str,
    records_by_person: dict[str, list[dict]],
    roster: list[dict],
    taxonomy: Taxonomy,
) -> None:
    """Each sighting raw, beside its derivation. Never fatal."""
    try:
        stored = await insert_source_records(
            request_id,
            jurisdiction_ocdid,
            records_by_person,
            taxonomy,
            images_by_person(roster),
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


async def _update_last_seen_at(
    cur, request_id: str, changes: list[ProposedChange], last_seen_at
) -> None:
    """Record that a scrape still found these people where we already hold them."""
    advanced = await memberships_db.advance_last_seen_at(
        cur, still_held(changes), last_seen_at
    )
    logger.info(f"[{request_id}] Advanced last_seen_at on {advanced} membership(s)")


async def _close_absent_holders(
    cur,
    request_id: str,
    jurisdiction_ocdid: str,
    changes: list[ProposedChange],
    last_seen_at,
) -> None:
    """Close anyone this scrape stopped naming.

    Transaction time, like `last_seen_at` above and for the same reason: `closed_at` records
    that we stopped seeing someone, not a claim that they left — that claim is `end_date`, and
    it comes from the source. An observation does not wait for review.

    An empty roster closes nobody, which `close_absent` guards.
    """
    closed = await memberships_db.close_absent(
        cur, jurisdiction_ocdid, still_listed(changes), last_seen_at
    )
    if closed:
        logger.info(f"[{request_id}] Closed {closed} membership(s) no longer listed")


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
    """
    try:
        roster = [Person(**record) for record in records]
        # A pick only exists on a roster a reviewer has edited, so this is almost always
        # empty at ingest — but a re-submit of an edited roster must not undo the pick.
        derived = derived_posts(roster, taxonomy, roles, await chosen_posts(roster))
        await posts_db.find_or_create_all(jurisdiction_ocdid, derived)
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

    await update_pipeline_run_data(request.request_id, updated_data)
    await _store_source_records(
        request.request_id,
        request.jurisdiction_ocdid,
        records_by_person,
        updated_data,
        taxonomy,
    )
    derived = await _find_or_create_posts(
        request.request_id, request.jurisdiction_ocdid, updated_data, roles, taxonomy
    )
    await _apply_scrape_changes(request.request_id, request.jurisdiction_ocdid, derived)
    await _record_resolved_url(
        request.request_id, request.jurisdiction_ocdid, workflow_context
    )

    review_json = await _review_summary(updated_data, workflow_context, roles)
    await update_pipeline_run_review_json(request.request_id, review_json)

    for issue in workflow_context.get("data", {}).get("issues", []):
        await upsert_issue(request.request_id, issue["type"], [issue.get("data") or {}])


async def _apply_scrape_changes(
    request_id: str, jurisdiction_ocdid: str, derived: list[DerivedPost]
) -> None:
    """Never fatal, like the other derived writes: a scrape whose people are stored must not
    error over a timestamp.

    One transaction: the writes below share a single `last_seen_at` and describe one reading of
    who holds what. Applying half of it would leave a roster no scrape ever saw.

    Run-level, not per-person: an absence has no page fetch to be dated by, so `closed_at` can
    only be `pipeline_runs.updated_at` — and it must match `last_seen_at` for the as-of window
    to compare them.
    """
    try:
        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            last_seen_at = await run_updated_at(cur, request_id)
            changes = await _get_proposed_changes(cur, jurisdiction_ocdid, derived)
            await _update_last_seen_at(cur, request_id, changes, last_seen_at)
            await _close_absent_holders(
                cur, request_id, jurisdiction_ocdid, changes, last_seen_at
            )
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
