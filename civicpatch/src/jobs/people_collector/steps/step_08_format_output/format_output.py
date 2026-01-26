from typing import List
from domain.models import person_to_official
from jobs.people_collector.schemas import (
  PeopleCollectorContext,
  WorkflowStatus,
  WorkflowConfig,
  FormatOutputStep,
)
import utils.log_utils as log_utils
from shared.utils.config_utils import get_divisions 

from domain.models import (
  Official,
  person_to_official
)

def format_output(context: PeopleCollectorContext) -> FormatOutputStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 8: {WorkflowStatus.FORMAT_OUTPUT} Formatting output data.")
    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    people = context.data.merge_records_across_llms_step.people

    data = [person_to_official(person) for person in people]

    # TODO: Make this more generic later
    division_configs = get_divisions()
    for i in range(len(data)):
        division_string = data[i].office.division_ocdid
        data[i].office.division_ocdid = normalize_division(jurisdiction_ocdid, division_string, division_configs)

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
        officials=data,
        config=config
    )

def normalize_division(jurisdiction_ocdid: str, division_string: str, division_configs) -> str:
    division_ocdid_base = jurisdiction_ocdid.replace("ocd-jurisdiction", "ocd-division")
    # Remove the jurisdiction type suffix (e.g "/government")
    division_ocdid_base = division_ocdid_base.rsplit('/', 1)[0]
    

    if not division_string:
        return division_ocdid_base

    division_parts = division_string.lower().split(' ')
    division_key = division_parts[0]
    if division_key in division_configs and division_configs[division_key].get("has_geographic_area", False):
        division_parts_suffix = '_'.join(division_parts[1:]).strip()
        division_name = division_configs[division_key].get("name", division_key)
        return f"{division_ocdid_base}/{division_name}:{division_parts_suffix}"
    else:
        return division_ocdid_base

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