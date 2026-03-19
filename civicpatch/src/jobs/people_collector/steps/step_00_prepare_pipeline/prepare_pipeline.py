import os
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

    # Create/clear cache folder
    cache_path = get_cache_path(jurisdiction_ocdid)
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)  # Recursively delete all files and subdirectories
    os.makedirs(cache_path, exist_ok=True)  # Recreate the folder

    # Create/clear images folder
    images_path = get_images_path(jurisdiction_ocdid)
    if os.path.exists(images_path):
        shutil.rmtree(images_path)
    os.makedirs(images_path, exist_ok=True)  # Recreate the folder

    data = await search_people(jurisdiction_ocdid, state="current")
    existing_people = [Person(**person) for person in data]

    logger.info(f"prepare_pipeline: {len(existing_people)} current people found in DB.")

    research_elected_officials = getattr(
        context.data.research_municipality_step, "elected_officials", []
    )

    roles_hint = get_roles_hint(research_elected_officials, existing_people)
    identities = person_list_to_identities(existing_people)
    source_urls = get_source_urls(existing_people)

    return PreparePipelineStep(
        roles_hint=roles_hint,
        identities=identities,
        source_urls=source_urls,
    )

def get_roles_hint(researched_officials: list[Official], people: list[Person]) -> list[str]:
    # If there are no people, use the researched officials data to get role hints for the LLMs
    if not people:
        roles_hint = set()
        for official in researched_officials:
            office = getattr(official, "office", None) or {}
            office_name = office.get("name", "")
            if office_name:
                roles_hint.add(office_name)
        return list(roles_hint)

    roles_hint = set()
    for person in people:
        office = getattr(person, "office", None) or {}
        office_name = office.get("name", "")
        if office_name:
            roles_hint.add(office_name)
    return list(roles_hint)

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
    source_urls = [url for url, count in url_counts.items() if count > 1]
    return set(source_urls)