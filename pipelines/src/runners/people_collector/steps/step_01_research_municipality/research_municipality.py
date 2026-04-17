from typing import List

import httpx

from runners.people_collector.schemas import (
    PeopleCollectorContext,
    PipelineStatus,
    ResearchMunicipalityLLMSchema,
    ResearchMunicipalityStep,
    ResearchedPerson,
)
import services.civicpatch_api as civicpatch_api
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
from shared.utils import config_utils
from shared.utils.name_utils import person_list_to_identities
from shared.schemas import Person
from utils import people_utils, log_utils
from utils.request_utils import with_retry

MINIMUM_ELECTED_OFFICIALS_NUM = 5
MAX_RETRIES = 5 # flakyLLM call

async def research_municipality(context: PeopleCollectorContext, api_client: httpx.AsyncClient) -> ResearchMunicipalityStep:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 1: {PipelineStatus.RESEARCH_MUNICIPALITY.value}")

    existing = await civicpatch_api.get_current_people(api_client, context.data.jurisdiction_ocdid)

    if existing:
        logger.info(f"research_municipality: using {len(existing)} existing DB people, skipping Gemini.")
        return _step_from_db(context.data.config, context.data.jurisdiction_ocdid, existing)
    else:
        return await _step_from_gemini(context, logger)


async def _step_from_gemini(context: PeopleCollectorContext, logger) -> ResearchMunicipalityStep:
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    prompt = google_gemini_prompt.research_municipality_prompt(jurisdiction_ocdid, context.data.config.name or "")

    # Tool call + JSON output doesn't work at the same time for Google Gemini,
    # let's retry a couple times til it works.
    people = await with_retry(
        logger, MAX_RETRIES,
        func=lambda: research_with_llm(context, prompt)
    )
    role_configs = config_utils.get_role_configs(context.data.role_config)
    target_people = people_utils.filter_people_by_roles(role_configs, people)

    return ResearchMunicipalityStep(
        expected_count=len(target_people),
        target_designations=people_utils.filter_geographic_designations(
            [d for p in target_people for d in p.designations]
        ),
        roles_hint=_roles_hint(target_people),
        identities={p.name: [] for p in people},
        source_urls=_source_urls(context.data.config, []),
    )


def _step_from_db(config, jurisdiction_ocdid: str, existing: list) -> ResearchMunicipalityStep:
    existing_people = [Person(**p) for p in existing]

    return ResearchMunicipalityStep(
        expected_count=len(existing),
        target_designations=list({
            d
            for p in existing
            for d in people_utils.division_ocdid_to_designation(
                (p.get("office") or {}).get("division_ocdid"), jurisdiction_ocdid
            )
        }),
        roles_hint=_roles_hint(existing_people),
        identities=person_list_to_identities(existing_people),
        source_urls=_source_urls(config, existing_people),
        origin_source="existing",
    )


async def research_with_llm(context: PeopleCollectorContext, prompt: str) -> List[ResearchedPerson]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Researching with LLM for jurisdiction {context.data.jurisdiction_ocdid}")

    response = await google_gemini_llm.run_prompt(
        context.request_id,
        context.data.jurisdiction_ocdid,
        prompt,
        response_schema=ResearchMunicipalityLLMSchema,
        with_search=True
    )

    if not response:
        raise ValueError("No response from LLM")
    people = response.get("people", [])

    return format_response(people)

def format_response(people: List[dict]) -> List[ResearchedPerson]:
    formatted_people = []
    for person in people:
        if not person.get("name"):
            continue
        formatted_people.append(ResearchedPerson.model_validate(person))
    return formatted_people

def _roles_hint(people) -> List[str]:
    # Works for both Person (office.name) and ResearchedPerson (roles list).
    # office_name_to_roles splits by " - " and keeps only config-recognized role names.
    seen = []
    for item in people:
        office_name = (
            (getattr(item, "office", None) or {}).get("name")
            or " - ".join(getattr(item, "roles", None) or [])
        )
        for role in people_utils.office_name_to_roles(office_name):
            if role not in seen:
                seen.append(role)
    return seen

def _source_urls(config, people: List[Person]) -> List[str]:
    if config.source_urls:
        return config.source_urls
    url_counts = {}
    for person in people:
        for url in (getattr(person, "source_urls", None) or []):
            url_counts[url] = url_counts.get(url, 0) + 1
    return [url for url, count in url_counts.items() if count > 1]
