import os
import json

from typing import List, Dict
from services import google_sheets_service
from schemas.requests import HandleSubmitJobArtifactsRequest
from schemas.responses import SubmitJobArtifactsResponse
import utils.file_utils as file_utils
import services.storage_service as storage_service
import services.github_service as github_service
import logging
import yaml

COST_BY_REQUEST_SHEET_NAME = "Cost By Request"
LLMS_SHEET_NAME = "Cost LLMs"
SEARCH_ENGINES_SHEET_NAME = "Cost Search Engines"
STORAGE_SHEET_NAME = "Cost Storage"

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
INSTANCE_DOMAIN = "civicpatch.org" # Just hardcode it for now...

logger = logging.getLogger(__name__)

async def handle_submit_job_artifacts(
        request: HandleSubmitJobArtifactsRequest, 
        background_tasks=None
) -> SubmitJobArtifactsResponse:
    file_suffix = request.file.filename

    artifact_file_patterns = [
        "data/*/local/*.yml",
        "data_source/*/local/*/workflow_context.json",
    ]
    debug_file_patterns = [
        "data_source/*/local/*/cache/*",
        "data_source/*/local/*/images/*",
        "data_source/*/local/*/costs.json",
        "data_source/*/local/*/workflow.log",
    ]

    zip_path, temp_dir = await file_utils.save_upload_to_temp(request.file)
    extracted_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extracted_dir, exist_ok=True)
    await file_utils.extract_zip(zip_path, extracted_dir)

    # Copy files to artifact_files (for zipping later)
    # Copy files to debug_files (for uploading individually to storage for debugging)
    artifact_file_dir = os.path.join(temp_dir, "artifact_files")
    debug_file_dir = os.path.join(temp_dir, "debug_files")

    file_utils.copy_files_preserving_hierarchy(extracted_dir, artifact_file_dir, patterns=artifact_file_patterns)
    file_utils.copy_files_preserving_hierarchy(extracted_dir, debug_file_dir, patterns=debug_file_patterns)

    # Validate expected files exist
    is_valid = await file_utils.validate_file_patterns(artifact_file_dir, artifact_file_patterns)
    if not is_valid:
        raise Exception(f"Uploaded zip file is missing expected files matching patterns: {artifact_file_patterns}")
    
    # For every file in debug_file_dir, upload to storage,
    # Including image files
    filenames_to_urls = await _upload_debug_files(debug_file_dir, request.request_id)
    data_file_path = file_utils.find_file(artifact_file_dir, "data/*/local/*.yml")
    with open(data_file_path, "r") as f:
        data = yaml.safe_load(f)
    updated_data = await _process_images(debug_file_dir, filenames_to_urls, data)
    with open(data_file_path, "w") as f:
        yaml.safe_dump(updated_data, f, sort_keys=False, allow_unicode=True)

    artifact_zip_path = await file_utils.zip_directory(artifact_file_dir, f"artifact_{file_suffix}")
    zip_file_key = f"{request.request_id}/{os.path.basename(artifact_zip_path)}"
    zip_file_url = await storage_service.upload_file_to_storage(
        "civicpatch-artifacts", 
        artifact_zip_path, 
        key=zip_file_key, 
        with_presigned_url=True
    )


    # Send costs to Google Sheets
    background_tasks.add_task(_send_costs, debug_file_dir)

    await github_service.trigger_github_data_intake_workflow(
            request.server_detail.user_email,
            request.server_detail.server_url,
            request_id=request.request_id,
            jurisdiction_ocdid=request.jurisdiction_ocdid,
            zip_file_url=zip_file_url,
        )

    return SubmitJobArtifactsResponse(
        filename=request.file.filename,
        status="uploaded",
        zip_file_url=zip_file_url,
        request_id=request.request_id,
        jurisdiction_ocdid=request.jurisdiction_ocdid
    )

async def _process_images(debug_file_dir: str, filenames_to_urls: dict, data: List[Dict]) -> List[Dict]:
    """
    Replace local image paths in data with their corresponding URLs from storage.

    Args:
        artifact_file_dir (str): The directory containing artifact files.
        debug_file_dir (str): The directory containing debug files.
        filenames_to_urls (dict): A mapping of original filenames to their URLs in storage.
        data (list): The list of person dictionaries to process.

    Returns:
        list: The updated list of person dictionaries with image URLs.
    """
    image_map_file = file_utils.find_file(debug_file_dir, "data_source/*/local/*/images/image_map.json")
    with open(image_map_file, "r") as f:
        image_map = json.load(f)

    for person in data:
        if person.get("image"):
            if person["image"] in image_map and image_map[person["image"]] in filenames_to_urls:
                storage_url = filenames_to_urls[image_map[person["image"]]]
                # convert storage URL to the civicpatch-artifacts bucket
                # temp TODO move
                cdn_image_url = storage_url.replace(f"{STORAGE_ENDPOINT}/civicpatch-artifacts", f"https://civicpatch-artifacts.{INSTANCE_DOMAIN}")

                person["cdn_image"] = cdn_image_url
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
    try:
        for root, _, files in os.walk(debug_file_dir):
            for file in files:
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, debug_file_dir)  # Preserve the hierarchy
                base_filename = os.path.basename(file_path)
                storage_key = f"{file_suffix_without_ext}/{relative_path}"  # Use request_id as the root folder
                url = await storage_service.upload_file_to_storage(
                    "civicpatch-artifacts",
                    file_path,
                    key=storage_key,
                    with_presigned_url=False
                )
                filename_to_url[base_filename] = url
    except Exception as e:
        logger.error(f"Failed to upload debug files for request {file_suffix_without_ext}: {e}")

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

