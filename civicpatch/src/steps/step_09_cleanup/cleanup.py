import os
import shutil
import json
from typing import List, cast

from utils.data_path_utils import get_data_source_municipality_path
from schemas import PipelineContext, PipelineStatus, Person, MergeRecordsAcrossLLMsStep
from utils import url_utils, log_utils, cost_utils

def cleanup(context: PipelineContext):
    # Remove files under data_source/cache and data_source/images
    jurisdiction_id = context.jurisdiction_id
    logger = log_utils.get_pipeline_logger(jurisdiction_id)
    logger.info(f"Step 9: {PipelineStatus.CLEANUP.value}")
    request_id = context.request_id
    data_source_dir = get_data_source_municipality_path(jurisdiction_id)
    cache_dir = os.path.join(data_source_dir, "cache")
    images_dir = os.path.join(data_source_dir, "images")

    merge_records_step = cast(MergeRecordsAcrossLLMsStep,context.steps[PipelineStatus.MERGE_RECORDS_ACROSS_LLMS])
    people_data = merge_records_step.people
    people = [Person.parse_obj(person) for person in people_data]

    if os.path.exists(cache_dir):
        # Only keep cache folders that are referenced by people
        cleanup_cache(cache_dir, people)
    if os.path.exists(images_dir):
        # Only keep images that are referenced by people
        cleanup_images(logger, request_id, jurisdiction_id, images_dir, people)

def cleanup_cache(cache_dir: str, people_list: List[Person]):
    # Clear out any page urls are not under sources or website urls
    pages_to_keep = set()

    for person in people_list:
        for source in person.sources:
            pages_to_keep.add(source)
        if person.website:
            pages_to_keep.add(person.website)

    pages_to_keep = set(url_utils.format_url_to_folder(url) for url in pages_to_keep)

    for folder in os.listdir(cache_dir):
        folder_path = os.path.join(cache_dir, folder)
        if os.path.isdir(folder_path):
            if folder not in pages_to_keep:
                shutil.rmtree(folder_path)

def cleanup_images(logger, request_id, jurisdiction_id, images_dir: str, people_list: List[Person]):
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
                    file_size_bytes=os.path.getsize(image_file_path)
                )

    missing_images = images_to_keep - images_found
    if len(missing_images) > 0:
        logger.error(f"Missing images that were expected to be found: {missing_images}")

    return {}
