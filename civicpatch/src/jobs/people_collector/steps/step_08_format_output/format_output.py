from typing import List, Tuple

import services.civicpatch_api
import utils.log_utils as log_utils
import utils.people_utils as people_utils
from domain.models import Official
from jobs.people_collector.schemas import (
    FormatOutputStep,
    PeopleCollectorContext,
    WorkflowConfig,
    WorkflowStatus,
)
from shared.utils.config_utils import get_designations


async def format_output(context: PeopleCollectorContext) -> FormatOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 8: {WorkflowStatus.FORMAT_OUTPUT} Formatting output data.")
    designation_configs = get_designations()

    data = context.data.merge_records_across_llms_step.people

    people = [
        people_utils.person_to_official(designation_configs, person) for person in data
    ]

    filtered_people = [
        person for person in people if not person.name == "Vacant Vacant"
    ]

    # TODO: Make this more generic later
    for person in filtered_people:
        person = maybe_add_fallback_url(person)

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

    return FormatOutputStep(officials=filtered_people)


def maybe_add_fallback_url(person: Official) -> Official:
    if not person.urls and person.source_urls:
        person.urls = [person.source_urls[0]]
    return person
