import json
import os
from typing import List

import services.civicpatch_api
import utils.log_utils as log_utils
import utils.people_utils as people_utils
from domain.models import Official
from jobs.people_collector.schemas import (
    FormatOutputStep,
    PeopleCollectorContext,
    PipelineStatus,
)
from shared.utils.config_utils import get_designations
import shared.utils.data_path_utils as data_path_utils


async def format_output(context: PeopleCollectorContext) -> FormatOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 8: {PipelineStatus.FORMAT_OUTPUT} Formatting output data.")
    designation_configs = get_designations()

    data = context.data.merge_records_across_llms_step.people

    people = [
        people_utils.person_to_official(designation_configs, person) for person in data
    ]

    filtered_people = [
        person for person in people
        if len(person.name.split()) >= 2
    ]

    image_map = _get_image_map(context.data.jurisdiction_ocdid, logger)
    for person in filtered_people:
        person = _swap_local_image(person, image_map)
        person = _maybe_add_fallback_url(person)

    resolved_people = await services.civicpatch_api.batch_resolve_people(
        context.data.jurisdiction_ocdid,
        filtered_people,
    )
    logger.debug(f"Batch resolved people data from API: {resolved_people}")
    logger.debug(
        f"Filtered people before assigning IDs: {[person.model_dump() for person in filtered_people]}"
    )
    for person, resolved_person in zip(filtered_people, resolved_people):
        person.id = resolved_person.get("id")
        existing = resolved_person.get("person")
        if existing and not resolved_person.get("ambiguous"):
            existing_name = existing.get("name") if isinstance(existing, dict) else existing.name
            existing_other_names = (existing.get("other_names") if isinstance(existing, dict) else existing.other_names) or []
            names_differ = existing_name and existing_name != person.name
            extra_names = (
                ([person.name] if names_differ else [])
                + ([existing_name] if names_differ else [])
                + list(existing_other_names)
            )
            person.other_names = list(dict.fromkeys(person.other_names + extra_names))

    return FormatOutputStep(officials=filtered_people)


def _maybe_add_fallback_url(person: Official) -> Official:
    if not person.urls and person.source_urls:
        person.urls = [person.source_urls[0]]
    return person


def _get_image_map(jurisdiction_ocdid: str, logger) -> dict:
    try:
        images_dir = data_path_utils.get_images_path(jurisdiction_ocdid)
    except FileNotFoundError as e:
        logger.warning(f"_get_image_map: data_source dir not found: {e}")
        return {}
    map_file = os.path.join(images_dir, "image_map.json")
    logger.info(f"_get_image_map: looking for image_map at {map_file}")
    if not os.path.exists(map_file):
        logger.warning(f"_get_image_map: image_map.json not found at {map_file}")
        return {}
    with open(map_file, "r") as f:
        image_map = json.load(f)
    logger.info(f"_get_image_map: loaded {len(image_map)} entries")
    return image_map


def _swap_local_image(official: Official, image_map: dict) -> Official:
    if not official.image or not official.image.startswith("local://"):
        return official
    basename = official.image.removeprefix("local://")
    if basename not in image_map:
        return official
    official.cdn_image = official.image
    official.image = image_map[basename]
    return official
