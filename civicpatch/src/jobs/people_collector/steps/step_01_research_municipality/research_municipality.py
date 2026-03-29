from typing import List, Dict
from jobs.people_collector.schemas import (
    PeopleCollectorContext,
    WorkflowStatus,
    ResearchMunicipalityLLMSchema,
    ResearchMunicipalityStep,
    ResearchedPerson,
    ProgressState,
)
import services.civicpatch_api as civicpatch_api
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
from shared.utils import config_utils
from utils import people_utils, log_utils
from utils.request_utils import with_retry

MINIMUM_ELECTED_OFFICIALS_NUM = 5

async def research_municipality(context: PeopleCollectorContext) -> ResearchMunicipalityStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 1: {WorkflowStatus.RESEARCH_MUNICIPALITY.value}")

    jurisdiction_ocdid = context.data.jurisdiction_ocdid

    existing = await civicpatch_api.get_current_people(jurisdiction_ocdid)
    if existing:
        logger.info(f"research_municipality: using {len(existing)} existing DB people, skipping Gemini.")
        researched = [
            ResearchedPerson(name=p["name"], roles=[], designations=[])
            for p in existing
        ]
        return ResearchMunicipalityStep(
            people=researched,
            elected_officials=researched,
            origin_source="existing",
        )

    municipality_name = context.data.config.name

    # Tool call + JSON output doesn't work at the same time for Google Gemini,
    # let's retry a couple times til it works.
    prompt = google_gemini_prompt.research_municipality_prompt(jurisdiction_ocdid, municipality_name)

    MAX_RETRIES = 5
    people = await with_retry(
        logger, MAX_RETRIES,
        func=lambda: research_with_llm(context, prompt)
    )
    role_configs = config_utils.get_role_configs()
    target_people = people_utils.filter_people_by_roles(role_configs, people)

    return ResearchMunicipalityStep(
        people=people,
        elected_officials=target_people,
    )

async def research_with_llm(context: PeopleCollectorContext, prompt: str) -> List[ResearchedPerson]:
    """
    Research the municipality using the LLM.
    """
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
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
        if person.get("name") is None:
            person["name"] = "Vacant Vacant"
        formatted_people.append(ResearchedPerson.model_validate(person))
    return formatted_people
