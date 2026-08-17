import os
import json

from typing import List, Dict
import lib.sheets as google_sheets_service
from schemas.pipeline_runs import HandleSubmitPipelineRunArtifactsRequest
from schemas.pipeline_runs import SubmitPipelineRunArtifactsResponse
import lib.files as file_utils
import shared.utils.id_utils
import shared.utils.config_utils
import lib.storage as storage_service
import lib.github.api as github_service
from database.pipeline_runs import update_pipeline_run_data, update_pipeline_run_review_json, update_pipeline_run_status
from database.issues import upsert_issue
from database.roles import get_roles
from database.source_records import insert_source_records
from services.publish import commit_unreviewed_scrape
from shared.schemas import Official, RoleConfig
from shared.utils.taxonomy import build_taxonomy
from shared.utils.statuses import PipelineIssueType, PipelineRunStatus
import logging
from shared.utils.yaml_utils import yaml_dump, yaml_load

import environment

COST_BY_REQUEST_SHEET_NAME = "Cost By Request"
LLMS_SHEET_NAME = "Cost LLMs"

PUBLIC_BUCKET = "civicpatch-artifacts"
PRIVATE_BUCKET = "civicpatch-debug"

INSTANCE_DOMAIN = "civicpatch.org" # Just hardcode it for now...

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


async def _store_source_records(request_id: str, records: list[dict]) -> None:
    """Append the evidence this scrape produced: each Record raw, beside its derivation.

    Never fatal. `source_records` is what 2.5 derives from and what triage reads unresolved
    labels out of — losing a scrape's evidence is bad, but failing the submit that carries
    the people is worse, so this logs and lets the rest of intake finish.
    """
    try:
        taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
        officials = [Official(**record) for record in records]
        stored = await insert_source_records(request_id, officials, taxonomy)
        logger.info(f"[{request_id}] Stored {stored} source record(s)")
    except Exception as e:
        logger.error(f"[{request_id}] Failed to store source records: {e}", exc_info=True)


async def _commit_unreviewed_copy(request_id: str, jurisdiction_ocdid: str) -> None:
    """Queue the scrape's write to open-data, at its unreviewed path.

    Never fatal: the roster is already in the database, and only the queueing happens here —
    the write itself is retried by Temporal until it lands.
    """
    try:
        await commit_unreviewed_scrape(request_id, jurisdiction_ocdid)
    except Exception as e:
        # Deliberately not fatal: the roster and its evidence are already in the database, so
        # failing the submit would mark a successful scrape as errored over a missing copy.
        # This is the one failure the workflow's retry policy cannot cover — no workflow
        # exists to retry — so it is the log line to alert on.
        logger.error(f"[{request_id}] Failed to queue unreviewed copy: {e}", exc_info=True)


async def _handle_submit_pipeline_run_artifacts(
        request: HandleSubmitPipelineRunArtifactsRequest,
) -> SubmitPipelineRunArtifactsResponse:
    file_suffix = shared.utils.id_utils.make_git_branch(request.jurisdiction_ocdid, request.request_id)

    pull_request_file_patterns = [
        "data/*/local/*.yml",
        "data_source/*/local/*/pipeline_run_context.json",
    ]

    image_file_patterns = [
        "data_source/*/local/*/images/*",
    ]

    artifact_file_patterns = pull_request_file_patterns

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

    # Copy files to artifact_files (for zipping later)
    # Copy files to debug_files (for uploading individually to storage for debugging)
    pull_request_file_dir = os.path.join(temp_dir, "pull_request_files")
    debug_file_dir = os.path.join(temp_dir, "debug_files")
    image_file_dir = os.path.join(temp_dir, "image_files")

    file_utils.copy_files_preserving_hierarchy(extracted_dir, pull_request_file_dir, patterns=pull_request_file_patterns)
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
        is_valid = await file_utils.validate_file_patterns(pull_request_file_dir, artifact_file_patterns)
        if not is_valid:
            raise Exception(f"Uploaded zip file is missing expected files matching patterns: {artifact_file_patterns}")

        data_file_path = file_utils.find_file(pull_request_file_dir, "data/*/local/*.yml")
        with open(data_file_path, "r") as f:
            data = yaml_load(f.read())
        updated_data = await _process_images(debug_file_dir, filenames_to_urls, data)
        with open(data_file_path, "w") as f:
            f.write(yaml_dump(updated_data))
        await update_pipeline_run_data(request.request_id, updated_data)
        await _store_source_records(request.request_id, updated_data)
        await _commit_unreviewed_copy(request.request_id, request.jurisdiction_ocdid)

        review_json = workflow_context.get("data", {}).get("review_output_step", {})
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


    artifact_zip_path = await file_utils.zip_directory(pull_request_file_dir, f"artifact_{file_suffix}.zip")
    zip_file_key = f"{request.request_id}/{os.path.basename(artifact_zip_path)}"
    zip_file_url = await storage_service.upload_file_to_storage(
        PUBLIC_BUCKET,
        artifact_zip_path,
        key=zip_file_key,
        with_presigned_url=True
    )

    if is_success:
        try:
            await github_service.trigger_github_data_intake_workflow(
                request.server_detail.user_email,
                request_id=request.request_id,
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                zip_file_url=zip_file_url,
                env=request.env,
            )
        except Exception as e:
            logger.error(f"[{request.request_id}] Failed to trigger data intake workflow: {e}", exc_info=True)

    return SubmitPipelineRunArtifactsResponse(
        filename=file_suffix,
        status="uploaded",
        zip_file_url=zip_file_url,
        request_id=request.request_id,
        jurisdiction_ocdid=request.jurisdiction_ocdid,
    )

async def _process_images(debug_file_dir: str, filenames_to_urls: dict, data: List[Dict]) -> List[Dict]:
    env = environment.get_env_vars()
    STORAGE_ENDPOINT = env["STORAGE_ENDPOINT"]

    for person in data:
        raw_cdn_image = person.get("cdn_image")
        if not raw_cdn_image or not raw_cdn_image.startswith("local://"):
            continue
        basename = raw_cdn_image.removeprefix("local://")
        if basename not in filenames_to_urls:
            logger.warning("_process_images: basename not in filenames_to_urls for person %s: %s", person.get("id"), raw_cdn_image)
            continue
        storage_url = filenames_to_urls[basename]
        person["cdn_image"] = storage_url.replace(f"{STORAGE_ENDPOINT}/{PUBLIC_BUCKET}", f"https://{PUBLIC_BUCKET}.{INSTANCE_DOMAIN}")
    return data

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

