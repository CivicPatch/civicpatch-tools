import os
import re
import shutil
from domain.models import Official
from jobs.people_collector.schemas import PeopleCollectorContext, PreparePipelineStep, WorkflowConfig, WorkflowStatus
from shared.utils.data_path_utils import get_cache_path, get_images_path
from services.civicpatch_api import search_people
from shared.utils.name_utils import person_list_to_identities
from shared.schemas import Person
from utils import log_utils

async def prepare_pipeline(context: PeopleCollectorContext) -> PreparePipelineStep:
    """
    Prepare the pipeline context for the next steps.

    This includes:
    - Registering the job with api.civicpatch.org, if applicable.
    - Emptying the log file for the jurisdiction.
    """
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 0: {WorkflowStatus.INIT.value}")

    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    # Empty log file, if it exists
    logger = log_utils.get_workflow_logger(jurisdiction_ocdid)
    logger.clear()

    reset_folder(get_cache_path(jurisdiction_ocdid))
    reset_folder(get_images_path(jurisdiction_ocdid))

    data = await search_people(jurisdiction_ocdid, state="current")
    existing_people = [Person(**person) for person in data]

    logger.info(f"prepare_pipeline: {len(existing_people)} current people found in DB.")

    research_elected_officials = getattr(
        context.data.research_municipality_step, "elected_officials", []
    )
    roles_hint = get_roles_hint(research_elected_officials, existing_people)
    identities = get_identities(research_elected_officials, existing_people)
    source_urls = get_source_urls(context.data.config, existing_people)

    return PreparePipelineStep(
        roles_hint=roles_hint,
        identities=identities,
        source_urls=source_urls,
    )

def reset_folder(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)

def get_roles_hint(researched_officials: list[Official], people: list[Person]) -> list[str]:
    source = people if people else researched_officials
    return list({
        office_name
        for item in source
        if (office_name := (getattr(item, "office", None) or {}).get("name", ""))
        and not _is_designation_specific(office_name)
    })

def _is_designation_specific(office_name: str) -> bool:
    # Filter out names containing digits or standalone single letters (e.g. "Place 6", "District A")
    return bool(re.search(r'\d', office_name)) or bool(re.search(r'\b[A-Za-z]\b', office_name))

def get_identities(researched_officials: list[Official], people: list[Person]) -> dict[str, list[str]]:
    if not people:
        return {official.name: [official.name] for official in researched_officials}
    return person_list_to_identities(people)

def get_source_urls(config: WorkflowConfig, people: list[Person]) -> list[str]:
    # If workflow config is avaliable, use that
    if config.source_urls:
        return config.source_urls

    # Identify source URLs that are present in multiple people profiles.
    # These are most likely to be directory listings.
    url_counts = {}
    for person in people:
        for url in person.source_urls:
            url_counts[url] = url_counts.get(url, 0) + 1
    return [url for url, count in url_counts.items() if count > 1]