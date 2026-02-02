
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

from domain.models import (
  Official
)

def format_output(context: PeopleCollectorContext) -> FormatOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 8: {WorkflowStatus.FORMAT_OUTPUT} Formatting output data.")
    designation_configs = get_designations()

    data = context.data.merge_records_across_llms_step.people

    people = [people_utils.person_to_official(designation_configs, person) for person in data]

    # TODO: Make this more generic later
    for person in people:
        person = maybe_add_fallback_url(person)

    identities = generate_identities_config(people)
    source_urls = find_source_urls(people)

    config = WorkflowConfig(
        url = context.data.config.url,
        name = context.data.config.name,
        source_urls = source_urls,
        identities = identities,

        # TODO: implement
        # should_crawl = context.data.config.should_crawl
    )

    return FormatOutputStep(
        officials=people,
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