import os
import json

from typing import List, Dict
import lib.sheets as google_sheets_service
from schemas.pipeline_runs import HandleSubmitPipelineRunArtifactsRequest
from schemas.pipeline_runs import SubmitPipelineRunArtifactsResponse
import lib.files as file_utils
import lib.buckets as buckets
import lib.storage as storage_service
from database.pipeline_runs import update_pipeline_run_data, update_pipeline_run_review_json, update_pipeline_run_status
from database.issues import upsert_issue
from database.roles import get_roles
from database.people import get_people_for_jurisdiction
from database.source_records import insert_source_records
from database import divisions as divisions_db
from database import organizations as organizations_db
from database import posts as posts_db
from database.database import get_pool
from core.ingest_people import (
    identified,
    local_image_basename,
    officials_from_rows,
    with_images,
)
from core.post_derivation import derived_posts
from services.jurisdiction_url import record_resolved_url, resolved_url
from shared.schemas import Official, RoleConfig
from shared.utils.config_utils import get_unique_roles
from shared.utils.name_utils import person_list_to_identities
from shared.utils.review_utils import ReviewInputs, build_review_summary
from shared.utils.person_id_utils import resolve_people_ids
from shared.utils.taxonomy import build_taxonomy
from shared.utils.statuses import PipelineIssueType, PipelineRunStatus
import logging
from shared.utils.yaml_utils import yaml_dump, yaml_load

import environment

COST_BY_REQUEST_SHEET_NAME = "Cost By Request"
LLMS_SHEET_NAME = "Cost LLMs"

PUBLIC_BUCKET = buckets.ARTIFACTS
PRIVATE_BUCKET = buckets.DEBUG

INSTANCE_DOMAIN = "civicpatch.org" # Just hardcode it for now...

# The value `people.status` is checked against; the column's CHECK constraint is the guard.
ACTIVE_PERSON_STATUS = "active"

IMAGE_MAP_PATTERN = "data_source/*/local/*/images/image_map.json"

logger = logging.getLogger(__name__)


async def handle_submit_pipeline_run_artifacts(
        request: HandleSubmitPipelineRunArtifactsRequest,
) -> SubmitPipelineRunArtifactsResponse:
    try:
        return await _handle_submit_pipeline_run_artifacts(request)
    except Exception as e:
        logger.error(f"[{request.request_id}] Artifact submission failed: {e}", exc_info=True)
        await update_pipeline_run_status(request.request_id, status=PipelineRunStatus.ERROR, progress=None)
        await upsert_issue(request.request_id, PipelineIssueType.PIPELINE_ERROR, [{"error": str(e)}])
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
    jurisdiction_ocdid: str, rows: list[dict], workflow_context: dict
) -> tuple[list[dict], dict[str, list[dict]]]:
    """The roster this submit means, whichever shape it arrived in.

    Fatal on failure, unlike the writes below: everything downstream consumes it.
    """
    taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
    identities = await _identities(jurisdiction_ocdid, workflow_context)
    roster, records_by_name = officials_from_rows(
        rows, identities, taxonomy, jurisdiction_ocdid, logger
    )
    identified_roster = await _assign_ids(jurisdiction_ocdid, roster)
    return identified_roster, _records_by_person(identified_roster, records_by_name)


def _records_by_person(roster: list[dict], records_by_name: dict) -> dict[str, list[dict]]:
    """Rekey the records from the name they grouped on to the id that name resolved to."""
    return {
        person["id"]: records_by_name[person["name"]]
        for person in roster
        if person["name"] in records_by_name
    }


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


async def _review_summary(roster: list[dict], workflow_context: dict) -> dict:
    """The issues a reviewer sees.

    Runs after reconciliation because every check counts people. Compared against the research
    step's identities, not ours: "absent" means this run did not find who it set out to.

    Never fatal — the people are already stored by now.
    """
    try:
        return await _build_review_summary(roster, workflow_context)
    except Exception as e:
        logger.error(f"Failed to build review summary: {e}", exc_info=True)
        return {}


async def _build_review_summary(roster: list[dict], workflow_context: dict) -> dict:
    research = workflow_context.get("data", {}).get("research_municipality_step") or {}
    identities = research.get("identities") or {}
    summary = build_review_summary(
        [{"name": name} for name in identities],
        roster,
        ReviewInputs(
            identities=identities,
            unique_roles=get_unique_roles(RoleConfig(roles=await get_roles())),
        ),
        research.get("origin_source") or "google_gemini",
    )
    # `Issue` is a model and this goes to `json.dumps`.
    return {**summary, "issues": [issue.model_dump() for issue in summary["issues"]]}


async def _store_source_records(
    request_id: str,
    jurisdiction_ocdid: str,
    records_by_person: dict[str, list[dict]],
) -> None:
    """Each sighting raw, beside its derivation. Never fatal."""
    try:
        taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
        stored = await insert_source_records(
            request_id, jurisdiction_ocdid, records_by_person, taxonomy
        )
        logger.info(f"[{request_id}] Stored {stored} source record(s)")
    except Exception as e:
        logger.error(f"[{request_id}] Failed to store source records: {e}", exc_info=True)


async def _find_or_create_posts(
    request_id: str, jurisdiction_ocdid: str, records: list[dict]
) -> None:
    """Derive the posts this scrape implies and write them, so review has real posts to
    point a person at.

    Here rather than at publish because the Post picker can only offer posts that exist, and
    review comes first. Memberships stay at publish: a post can be proposed, a membership is
    only true once accepted. Never fatal — posts are re-derivable from `source_records`.
    """
    try:
        roles = await get_roles()
        taxonomy = build_taxonomy(RoleConfig(roles=roles))
        officials = [Official(**record) for record in records]
        specs = derived_posts(officials, taxonomy, roles)

        pool = await get_pool()
        async with pool.connection() as conn, conn.cursor() as cur:
            organization_id = await organizations_db.find_or_create(cur, jurisdiction_ocdid)
            for spec in specs:
                await divisions_db.find_or_create(cur, spec.division_ocdid, jurisdiction_ocdid)
                await posts_db.find_or_create(
                    cur,
                    jurisdiction_ocdid,
                    organization_id,
                    spec.role_id,
                    spec.division_ocdid,
                    headcount=spec.headcount,
                )
            await conn.commit()
        logger.info(f"[{request_id}] Derived {len(specs)} post(s)")
    except Exception as e:
        logger.error(f"[{request_id}] Failed to derive posts: {e}", exc_info=True)


async def _record_resolved_url(request_id: str, jurisdiction_ocdid: str, workflow_context: dict) -> None:
    """Point the registry at wherever the scrape found the jurisdiction. Never fatal."""
    url = resolved_url(workflow_context)
    if not url:
        return
    try:
        await record_resolved_url(jurisdiction_ocdid, url)
    except Exception as e:
        logger.error(f"[{request_id}] Failed to record resolved URL: {e}", exc_info=True)


async def _handle_submit_pipeline_run_artifacts(
        request: HandleSubmitPipelineRunArtifactsRequest,
) -> SubmitPipelineRunArtifactsResponse:
    # What the scrape produced and we publish: the rendered roster, plus the run context the
    # review summary and resolved URL are read out of.
    output_file_patterns = [
        "data/*/local/*.yml",
        "data_source/*/local/*/pipeline_run_context.json",
    ]

    image_file_patterns = [
        "data_source/*/local/*/images/*",
    ]

    debug_file_patterns = [
        "data_source/*/local/*/cache/*",
        "data_source/*/local/*/costs.json",
        "data_source/*/local/*/pipeline_run.log",
        "data_source/*/local/*/pipeline_run_context.json",
    ]

    zip_path = request.zip_path
    temp_dir = request.temp_dir
    extracted_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extracted_dir, exist_ok=True)
    await file_utils.extract_zip(zip_path, extracted_dir)

    # Three destinations, three fates: output is read and published, images are uploaded and
    # become each person's cdn_image, debug files are uploaded individually for the run log,
    # run context and per-source markdown the UI links to.
    output_file_dir = os.path.join(temp_dir, "output_files")
    debug_file_dir = os.path.join(temp_dir, "debug_files")
    image_file_dir = os.path.join(temp_dir, "image_files")

    file_utils.copy_files_preserving_hierarchy(extracted_dir, output_file_dir, patterns=output_file_patterns)
    file_utils.copy_files_preserving_hierarchy(extracted_dir, debug_file_dir, patterns=debug_file_patterns)
    file_utils.copy_files_preserving_hierarchy(extracted_dir, image_file_dir, patterns=image_file_patterns)

    is_success = request.pipeline_run_status == PipelineRunStatus.SUCCESS

    filenames_to_urls = await _upload_files(image_file_dir, request.request_id, PUBLIC_BUCKET)
    await _upload_files(debug_file_dir, request.request_id, PRIVATE_BUCKET)

    try:
        await _send_costs(debug_file_dir)
    except Exception as e:
        logger.error(f"Failed to send costs for {request.request_id}: {e}", exc_info=True)

    try:
        context_path = file_utils.find_file(debug_file_dir, "data_source/*/local/*/pipeline_run_context.json")
        with open(context_path, "r") as f:
            workflow_context = json.load(f)
    except FileNotFoundError:
        workflow_context = {}

    if is_success:
        is_valid = await file_utils.validate_file_patterns(output_file_dir, output_file_patterns)
        if not is_valid:
            raise Exception(f"Uploaded zip file is missing expected files matching patterns: {output_file_patterns}")

        data_file_path = file_utils.find_file(output_file_dir, "data/*/local/*.yml")
        with open(data_file_path, "r") as f:
            data = yaml_load(f.read())
        roster, records_by_person = await _reconcile_roster(
            request.jurisdiction_ocdid, data, workflow_context
        )
        updated_data = await _process_images(image_file_dir, filenames_to_urls, roster)
        with open(data_file_path, "w") as f:
            f.write(yaml_dump(updated_data))
        await update_pipeline_run_data(request.request_id, updated_data)
        await _store_source_records(
            request.request_id, request.jurisdiction_ocdid, records_by_person
        )
        await _find_or_create_posts(
            request.request_id, request.jurisdiction_ocdid, updated_data
        )
        await _record_resolved_url(
            request.request_id, request.jurisdiction_ocdid, workflow_context
        )

        review_json = await _review_summary(updated_data, workflow_context)
        await update_pipeline_run_review_json(request.request_id, review_json)

        for issue in workflow_context.get("data", {}).get("issues", []):
            await upsert_issue(
                request.request_id,
                issue["type"],
                [issue.get("data") or {}],
            )
    else:
        context_data = workflow_context.get("data", {})
        error_step = context_data.get("error_step") or PipelineIssueType.PIPELINE_ERROR
        error_detail = context_data.get("error_detail") or {}
        await upsert_issue(request.request_id, error_step, [error_detail])


    # No data_intake dispatch, and no artifact zip. That Action opened the pull request a
    # scrape used to be reviewed through and then told us its number so a card could appear;
    # both jobs moved here, so the roster is committed to the unreviewed path directly and the
    # request carries its own review state.
    #
    # The zip existed only to give that Action a URL to fetch. Its contents — the rendered
    # roster and the run context — are now in `data_json` and on open-data, so zipping and
    # uploading them was work for no reader. The image and debug uploads above are separate
    # and stay: images become `cdn_image`, and the debug files back the run log, run context
    # and per-source markdown the UI links to.
    return SubmitPipelineRunArtifactsResponse(
        status="uploaded",
        request_id=request.request_id,
        jurisdiction_ocdid=request.jurisdiction_ocdid,
    )

def _read_image_map(image_file_dir: str) -> dict:
    """Downloaded filename to the url the photo was scraped from.

    Written by the scrape and shipped in the zip beside the images themselves, so cp.org can
    resolve provenance without the pipeline having done it first. Absent on a run that found
    no images, which is not an error.
    """
    try:
        path = file_utils.find_file(image_file_dir, IMAGE_MAP_PATTERN)
    except FileNotFoundError:
        return {}
    with open(path, "r") as f:
        return json.load(f)


async def _process_images(image_file_dir: str, filenames_to_urls: dict, data: List[Dict]) -> List[Dict]:
    """Turn each person's `local://` reference into the two urls a reader needs: where the
    photo came from, and where we serve it.

    Both halves happen here, off `image_map.json` and the uploaded files, both out of the zip.
    """
    env = environment.get_env_vars()
    storage_endpoint = env["STORAGE_ENDPOINT"]
    source_urls = _read_image_map(image_file_dir)
    cdn_urls = {
        basename: url.replace(
            f"{storage_endpoint}/{PUBLIC_BUCKET}",
            f"https://{PUBLIC_BUCKET}.{INSTANCE_DOMAIN}",
        )
        for basename, url in filenames_to_urls.items()
    }

    unserved = []
    for person in data:
        basename = local_image_basename(person)
        if basename and basename not in cdn_urls:
            unserved.append(str(person.get("name")))
    if unserved:
        logger.warning(f"_process_images: no uploaded image for {', '.join(unserved)}")

    return [with_images(person, source_urls, cdn_urls) for person in data]

async def _upload_files(source_dir: str, request_id: str, bucket: str) -> dict:
    filename_to_url = {}
    for root, _, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, source_dir)
            storage_key = f"{request_id}/{relative_path}"
            try:
                url = await storage_service.upload_file_to_storage(
                    bucket, file_path, key=storage_key, with_presigned_url=False
                )
                filename_to_url[os.path.basename(file_path)] = url
            except Exception as e:
                logger.error(f"Failed to upload {file_path} to {bucket} for request {request_id}: {e}")
    return filename_to_url

async def _send_costs(debug_file_dir: str):
    logging.info(f"Sending costs to Google Sheets from debug file directory: {debug_file_dir}")
    costs_file_path = file_utils.find_file(debug_file_dir, "data_source/*/local/*/costs.json")
    with open(costs_file_path, "r") as f:
        costs_data = json.load(f)

    total_cost_by_request = [list(costs_data.get("total_cost_by_request", {}).values())]
    llm_costs_flattened = [list(item.values()) for item in costs_data.get("llm_costs", [])]

    google_sheets_service.update_spreadsheet(COST_BY_REQUEST_SHEET_NAME, total_cost_by_request)
    google_sheets_service.update_spreadsheet(LLMS_SHEET_NAME, llm_costs_flattened)

