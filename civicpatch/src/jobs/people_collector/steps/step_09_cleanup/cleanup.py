import os
import shutil
import json
from typing import List, cast, Dict

from shared.utils.data_path_utils import get_data_source_path_for_jurisdiction_id
from jobs.people_collector.schemas import (
    PeopleCollectorContext, WorkflowStatus, MergeRecordsAcrossLLMsStep,

)
from utils import url_utils, log_utils, cost_utils
from domain.models import Official

# Todo: Should return updated configs
# TODO: should input things like "Official", etc...
def cleanup(context: PeopleCollectorContext):
    # Remove files under data_source/cache and data_source/images
    jurisdiction_id = context.data.jurisdiction_id
    logger = log_utils.get_workflow_logger(jurisdiction_id)
    logger.info(f"Step 9: {WorkflowStatus.CLEANUP.value}")
    request_id = context.request_id
    data_source_dir = get_data_source_path_for_jurisdiction_id(jurisdiction_id)
    cache_dir = os.path.join(data_source_dir, "cache")
    images_dir = os.path.join(data_source_dir, "images")

    people_data = context.data.format_output_step
    people = [Official.parse_obj(person) for person in people_data]

    if os.path.exists(cache_dir):
        # Only keep cache folders that are referenced by people
        cleanup_cache(cache_dir, people)
    if os.path.exists(images_dir):
        # Only keep images that are referenced by people
        cleanup_images(logger, request_id, jurisdiction_id, images_dir, people)

    updated_names = cleanup_names_config(context.data.identities)

    return {"identities": updated_names}


def cleanup_cache(cache_dir: str, people_list: List[Official]):
    # Clear out any page urls are not under sources or website urls
    pages_to_keep = set()

    for person in people_list:
        for source in person.source_urls:
            pages_to_keep.add(source)
        if person.urls:
            pages_to_keep.update(person.urls)

    pages_to_keep = set(url_utils.format_url_to_folder(url) for url in pages_to_keep)

    for folder in os.listdir(cache_dir):
        folder_path = os.path.join(cache_dir, folder)
        if os.path.isdir(folder_path):
            if folder not in pages_to_keep:
                shutil.rmtree(folder_path)


def cleanup_images(
    logger, request_id, jurisdiction_id, images_dir: str, people_list: List[Official]
):
    # Clear out any images that are not under image
    images_to_keep = set()
    image_map_file_path = os.path.join(images_dir, "image_map.json")
    image_map_data = {}

    with open(image_map_file_path, "r") as f:
        image_map_data = json.load(f)

    for person in people_list:
        if person.image is None:
            continue

        if person.image in image_map_data:
            images_to_keep.add(image_map_data[person.image])

    images_found = set()
    for image_file in os.listdir(images_dir):
        # Skip image_map.json
        if image_file == "image_map.json":
            continue

        image_file_path = os.path.join(images_dir, image_file)
        if os.path.isfile(image_file_path):
            if image_file_path not in images_to_keep:
                os.remove(image_file_path)
            else:
                images_found.add(image_file_path)
                cost_utils.add_storage_cost(
                    request_id=request_id,
                    jurisdiction_id=jurisdiction_id,
                    file_size_bytes=os.path.getsize(image_file_path),
                )

    missing_images = images_to_keep - images_found
    if len(missing_images) > 0:
        logger.error(f"Missing images that were expected to be found: {missing_images}")

    return {}


def cleanup_names_config(names_config: Dict[str, List[str]]) -> dict:
    # Remove any names that are empty or only whitespace
    cleaned_names_config = {}
    for key, names_list in names_config.items():
        if len(names_list) > 1:
            cleaned_names_config[key] = names_list
    return cleaned_names_config
