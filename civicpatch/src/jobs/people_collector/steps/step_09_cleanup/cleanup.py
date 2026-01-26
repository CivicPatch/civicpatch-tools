import os
import shutil
import json
from typing import List

from shared.utils.data_path_utils import get_data_source_path_for_jurisdiction_ocdid
from jobs.people_collector.schemas import (
    PeopleCollectorContext, WorkflowStatus, 

)
from utils import url_utils, log_utils
from domain.models import Official

# Todo: Should return updated configs
# TODO: should input things like "Official", etc...
def cleanup(context: PeopleCollectorContext):
    # Remove files under data_source/cache and data_source/images
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    logger = log_utils.get_workflow_logger(jurisdiction_ocdid)
    logger.info(f"Step 9: {WorkflowStatus.CLEANUP.value}")
    request_id = context.request_id
    data_source_dir = get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    cache_dir = os.path.join(data_source_dir, "cache")
    images_dir = os.path.join(data_source_dir, "images")

    people = context.data.format_output_step.officials

    if os.path.exists(cache_dir):
        # Only keep cache folders that are referenced by people
        cleanup_cache(cache_dir, people)
    if os.path.exists(images_dir):
        # Only keep images that are referenced by people
        cleanup_images(logger, request_id, jurisdiction_ocdid, images_dir, people)

    return


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
    logger, request_id, jurisdiction_ocdid, images_dir: str, people_list: List[Official]
):
    # Clear out any images that are not under image
    image_files_to_keep = set()
    # This is image source urls mapped to local file names
    image_map_file_path = os.path.join(images_dir, "image_map.json")
    image_map_data = {}
    missing_images = set()

    with open(image_map_file_path, "r") as f:
        image_map_data = json.load(f)

    for person in people_list:
        if person.image is None:
            continue

        if person.image in image_map_data:
            if not os.path.exists(image_map_data[person.image]):
                missing_images.add(image_map_data[person.image])
            image_files_to_keep.add(image_map_data[person.image])

    logger.debug(f"Image files to keep: {image_files_to_keep}")
    logger.debug(f"All image map data: {image_map_data}")
    for image_file in os.listdir(images_dir):
        logger.debug(f"Checking image file: {image_file}")
        # Skip image_map.json
        if image_file == "image_map.json":
            continue

        image_file_path = os.path.join(images_dir, image_file)
        if os.path.isfile(image_file_path):
            if image_file not in image_files_to_keep:
                logger.debug(f"Removing unreferenced image file: {image_file_path}")
                os.remove(image_file_path) 

    if len(missing_images) > 0:
        logger.error(f"Missing images that were expected to be found: {missing_images}")

    return {}

