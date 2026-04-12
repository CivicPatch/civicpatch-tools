import os
import json

from typing import List, Dict
from services import google_sheets_service
from schemas.requests import HandleSubmitJobArtifactsRequest
from schemas.responses import SubmitJobArtifactsResponse
import utils.file_utils as file_utils
import shared.utils.id_utils
import services.storage_service as storage_service
import services.github.github_api_service as github_service
from database.database import update_job_data, update_job_review_json, upsert_review_issue, update_job_status
from shared.utils.statuses import JobStatus
import logging
import yaml

import environment

COST_BY_REQUEST_SHEET_NAME = "Cost By Request"
LLMS_SHEET_NAME = "Cost LLMs"
SEARCH_ENGINES_SHEET_NAME = "Cost Search Engines"
STORAGE_SHEET_NAME = "Cost Storage"

INSTANCE_DOMAIN = "civicpatch.org" # Just hardcode it for now...

logger = logging.getLogger(__name__)

async def handle_submit_job_artifacts(
        request: HandleSubmitJobArtifactsRequest,
) -> SubmitJobArtifactsResponse:
    try:
        return await _handle_submit_job_artifacts(request)
    except Exception as e:
        logger.error(f"[{request.request_id}] Artifact submission failed: {e}", exc_info=True)
        await update_job_status(request.request_id, status=JobStatus.ERROR, progress=None)
        raise


async def _handle_submit_job_artifacts(
        request: HandleSubmitJobArtifactsRequest,
) -> SubmitJobArtifactsResponse:
    file_suffix = shared.utils.id_utils.make_git_branch(request.jurisdiction_ocdid, request.request_id)

    artifact_file_patterns = [
        "data/*/local/*.yml",
        "data_source/*/local/*/workflow_context.json",
    ]
    debug_file_patterns = [
        "data_source/*/local/*/cache/*",
        "data_source/*/local/*/images/*",
        "data_source/*/local/*/costs.json",
        "data_source/*/local/*/workflow.log",
        "data_source/*/local/*/workflow_context.json",
    ]

    zip_path = request.zip_path
    temp_dir = request.temp_dir
    extracted_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extracted_dir, exist_ok=True)
    await file_utils.extract_zip(zip_path, extracted_dir)

    # Copy files to artifact_files (for zipping later)
    # Copy files to debug_files (for uploading individually to storage for debugging)
    artifact_file_dir = os.path.join(temp_dir, "artifact_files")
    debug_file_dir = os.path.join(temp_dir, "debug_files")

    file_utils.copy_files_preserving_hierarchy(extracted_dir, artifact_file_dir, patterns=artifact_file_patterns)
    file_utils.copy_files_preserving_hierarchy(extracted_dir, debug_file_dir, patterns=debug_file_patterns)

    is_success = request.job_status == "SUCCESS"

    filenames_to_urls = await _upload_debug_files(debug_file_dir, request.request_id)

    try:
        await _send_costs(debug_file_dir)
    except Exception as e:
        logger.error(f"Failed to send costs for {request.request_id}: {e}", exc_info=True)

    if is_success:
        is_valid = await file_utils.validate_file_patterns(artifact_file_dir, artifact_file_patterns)
        if not is_valid:
            raise Exception(f"Uploaded zip file is missing expected files matching patterns: {artifact_file_patterns}")

        data_file_path = file_utils.find_file(artifact_file_dir, "data/*/local/*.yml")
        with open(data_file_path, "r") as f:
            data = yaml.safe_load(f)
        updated_data = await _process_images(debug_file_dir, filenames_to_urls, data)
        with open(data_file_path, "w") as f:
            yaml.safe_dump(updated_data, f, sort_keys=False, allow_unicode=True)
        await update_job_data(request.request_id, updated_data)

        workflow_context_path = file_utils.find_file(artifact_file_dir, "data_source/*/local/*/workflow_context.json")
        with open(workflow_context_path, "r") as f:
            workflow_context = json.load(f)
        review_json = workflow_context.get("data", {}).get("review_output_step", {})
        await update_job_review_json(request.request_id, review_json)

        unrecognized = (
            workflow_context.get("data", {})
            .get("merge_records_within_llm_step", {})
            .get("unrecognized_roles", [])
        )
        await upsert_review_issue(request.request_id, "unrecognized_role", unrecognized)

    else:
        try:
            workflow_context_path = file_utils.find_file(artifact_file_dir, "data_source/*/local/*/workflow_context.json")
            with open(workflow_context_path, "r") as f:
                workflow_context = json.load(f)
            dead_urls = workflow_context.get("data", {}).get("dead_urls", [])
            await upsert_review_issue(request.request_id, "dead_url", dead_urls)
        except FileNotFoundError:
            pass

    artifact_zip_path = await file_utils.zip_directory(artifact_file_dir, f"artifact_{file_suffix}.zip")
    zip_file_key = f"{request.request_id}/{os.path.basename(artifact_zip_path)}"
    zip_file_url = await storage_service.upload_file_to_storage(
        "civicpatch-artifacts",
        artifact_zip_path,
        key=zip_file_key,
        with_presigned_url=True
    )

    if is_success:
        try:
            await github_service.trigger_github_data_intake_workflow(
                request.server_detail.user_email,
                request.server_detail.server_url,
                request_id=request.request_id,
                jurisdiction_ocdid=request.jurisdiction_ocdid,
                zip_file_url=zip_file_url,
            )
        except Exception as e:
            logger.error(f"[{request.request_id}] Failed to trigger data intake workflow: {e}", exc_info=True)

    return SubmitJobArtifactsResponse(
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
        # convert storage URL to the civicpatch-artifacts bucket
        # temp TODO move
        person["cdn_image"] = storage_url.replace(f"{STORAGE_ENDPOINT}/civicpatch-artifacts", f"https://civicpatch-artifacts.{INSTANCE_DOMAIN}")
    return data

async def _upload_debug_files(debug_file_dir: str, file_suffix_without_ext: str) -> dict:
    """
    Upload files in debug_file_dir to storage and return a mapping of original filenames to their URLs.

    Args:
        debug_file_dir (str): Path to the directory containing debug files.
        file_suffix_without_ext (str): Suffix to use for naming files in storage.

    Returns:
        dict: A mapping of relative file paths to their URLs in storage.
    """
    filename_to_url = {}
    for root, _, files in os.walk(debug_file_dir):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, debug_file_dir)  # Preserve the hierarchy
            base_filename = os.path.basename(file_path)
            storage_key = f"{file_suffix_without_ext}/{relative_path}"  # Use request_id as the root folder
            try:
                url = await storage_service.upload_file_to_storage(
                    "civicpatch-artifacts",
                    file_path,
                    key=storage_key,
                    with_presigned_url=False
                )
                filename_to_url[base_filename] = url
            except Exception as e:
                logger.error(f"Failed to upload debug file {file_path} for request {file_suffix_without_ext}: {e}")

    logger.info("DEBUG: Uploaded debug files with the following URLs: %s", filename_to_url)
    return filename_to_url

async def _send_costs(debug_file_dir: str):
    logging.info(f"Sending costs to Google Sheets from debug file directory: {debug_file_dir}")
    costs_file_path = file_utils.find_file(debug_file_dir, "data_source/*/local/*/costs.json")
    with open(costs_file_path, "r") as f:
        costs_data = json.load(f)

    total_cost_by_request = [list(costs_data.get("total_cost_by_request", {}).values())]
    llm_costs_flattened = [list(item.values()) for item in costs_data.get("llm_costs", [])]
    search_engine_costs_flattened = [list(item.values()) for item in costs_data.get("search_engine_costs", [])]
    storage_costs_flattened = [list(item.values()) for item in costs_data.get("storage_costs", [])]

    google_sheets_service.update_spreadsheet(COST_BY_REQUEST_SHEET_NAME, total_cost_by_request)
    google_sheets_service.update_spreadsheet(LLMS_SHEET_NAME, llm_costs_flattened)
    google_sheets_service.update_spreadsheet(SEARCH_ENGINES_SHEET_NAME, search_engine_costs_flattened)
    google_sheets_service.update_spreadsheet(STORAGE_SHEET_NAME, storage_costs_flattened)

