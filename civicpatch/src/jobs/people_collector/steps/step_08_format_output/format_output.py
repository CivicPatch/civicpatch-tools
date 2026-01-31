
from domain.models import person_to_official
from jobs.people_collector.schemas import (
  PeopleCollectorContext,
  WorkflowStatus,
  WorkflowConfig,
  FormatOutputStep,
)
import utils.log_utils as log_utils
from shared.utils.config_utils import get_designations
from typing import List, Tuple

from domain.models import (
  Official,
  person_to_official
)

def format_output(context: PeopleCollectorContext) -> FormatOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 8: {WorkflowStatus.FORMAT_OUTPUT} Formatting output data.")
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    data = context.data.merge_records_across_llms_step.people

    people = [person_to_official(person) for person in data]

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

        government_type = context.data.research_municipality_step.government_type
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