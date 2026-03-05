
from domain.models import Person
from jobs.people_collector.schemas import (
  PeopleCollectorContext,
  WorkflowStatus,
  WorkflowConfig,
  FormatOutputStep,
)
import utils.log_utils as log_utils
import utils.people_utils as people_utils
from shared.utils.config_utils import get_designations
from typing import List, Tuple
import services.civicpatch_api

from domain.models import (
  Official
)

async def format_output(context: PeopleCollectorContext) -> FormatOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 8: {WorkflowStatus.FORMAT_OUTPUT} Formatting output data.")
    designation_configs = get_designations()

    data = context.data.merge_records_across_llms_step.people

    people = [people_utils.person_to_official(designation_configs, person) for person in data]

    filtered_people = [person for person in people if not person.name == "Vacant Vacant"]

    # TODO: Make this more generic later
    for person in filtered_people:
        person = maybe_add_fallback_url(person)

    resolved_people_response = await services.civicpatch_api.batch_resolve_people(
        context.data.jurisdiction_ocdid,
        filtered_people,
    )
    resolved_people = resolved_people_response.get("data", [])
    for person, resolved_person in zip(filtered_people, resolved_people):
        person.id = resolved_person.get("id")

    # TODO: get rid of this
    identities = generate_identities_config(filtered_people)
    source_urls = find_source_urls(filtered_people)
    config = WorkflowConfig(
        url = context.data.config.url,
        name = context.data.config.name,
        source_urls = source_urls,
        identities = identities,

        # TODO: implement
        # should_crawl = context.data.config.should_crawl
    )

    return FormatOutputStep(
        officials=filtered_people,
        config=config
    )

def maybe_add_fallback_url(person: Official) -> Official:
    if not person.urls and person.source_urls:
        person.urls = [person.source_urls[0]]
    return person

def generate_identities_config(people: List[Official]) -> dict:
    identities = {}
    for person in people:
        if person.name:
            identities[person.name] = person.other_names
    return identities

def find_source_urls(people: List[Official]) -> List[str]:
    source_urls = []
    for person in people:
        if person.source_urls:
            source_urls += person.source_urls

    return list(set(source_urls))