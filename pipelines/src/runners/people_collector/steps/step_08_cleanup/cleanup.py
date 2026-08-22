import json
import os
import shutil
from typing import List

from runners.people_collector.schemas import PeopleCollectorContext, PipelineStatus
from shared.schemas import LOCAL_IMAGE_PREFIX, PersonRecord
from shared.utils import url_utils
from shared.utils.data_path_utils import get_data_source_path_for_jurisdiction_ocdid
from utils import log_utils

IMAGE_MAP_FILE = "image_map.json"


def cleanup(context: PeopleCollectorContext):
    """Drop cached pages and downloaded images no record points at."""
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    logger = log_utils.get_pipeline_run_logger(jurisdiction_ocdid)
    logger.info(f"Step 9: {PipelineStatus.CLEANUP.value}")

    assert context.data.process_page_content_step is not None, (
        "should never happen — process_page_content_step is required before cleanup"
    )
    records = context.data.process_page_content_step.all_records()

    data_source_dir = get_data_source_path_for_jurisdiction_ocdid(jurisdiction_ocdid)
    cache_dir = os.path.join(data_source_dir, "cache")
    images_dir = os.path.join(data_source_dir, "images")

    if os.path.exists(cache_dir):
        cleanup_cache(cache_dir, records)
    if os.path.exists(images_dir):
        cleanup_images(logger, images_dir, records)


def cleanup_cache(cache_dir: str, records: List[PersonRecord]):
    urls = {record.source_url for record in records if record.source_url}
    urls.update(record.url for record in records if record.url)
    folders_to_keep = {url_utils.format_url_to_folder(url) for url in urls}

    for folder in os.listdir(cache_dir):
        folder_path = os.path.join(cache_dir, folder)
        if os.path.isdir(folder_path) and folder not in folders_to_keep:
            shutil.rmtree(folder_path)


def local_image_name(record: PersonRecord) -> str | None:
    if not record.image or not record.image.startswith(LOCAL_IMAGE_PREFIX):
        return None
    return record.image.removeprefix(LOCAL_IMAGE_PREFIX)


def cleanup_images(logger, images_dir: str, records: List[PersonRecord]):
    """Drop unreferenced files and the map entries that named them."""
    names = set()
    for record in records:
        name = local_image_name(record)
        if name:
            names.add(name)

    missing = {name for name in names if not os.path.exists(os.path.join(images_dir, name))}
    if missing:
        logger.error(f"Missing images that were expected to be found: {missing}")

    for image_file in os.listdir(images_dir):
        if image_file == IMAGE_MAP_FILE or image_file in names:
            continue
        path = os.path.join(images_dir, image_file)
        if os.path.isfile(path):
            os.remove(path)

    _prune_image_map(images_dir, names)


def _prune_image_map(images_dir: str, names: set):
    map_path = os.path.join(images_dir, IMAGE_MAP_FILE)
    if not os.path.exists(map_path):
        return
    with open(map_path, "r") as f:
        image_map = json.load(f)
    with open(map_path, "w") as f:
        json.dump({n: src for n, src in image_map.items() if n in names}, f)
