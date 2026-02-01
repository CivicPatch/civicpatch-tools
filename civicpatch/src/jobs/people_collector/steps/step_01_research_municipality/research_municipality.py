from typing import List, Dict
from jobs.people_collector.schemas import (
    PeopleCollectorContext,
    WorkflowStatus,
    ResearchMunicipalityLLMSchema,
    ResearchMunicipalityStep,
    ResearchedPerson,
    ProgressState,
)
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
from shared.utils import config_utils
from utils import people_utils, log_utils
import utils.request_utils as request_utils

MINIMUM_ELECTED_OFFICIALS_NUM = 5

async def research_municipality(context: PeopleCollectorContext) -> tuple[ProgressState, ResearchMunicipalityStep]:
    """
    Research the municipality to gather necessary data for further processing.
    """
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 1: {WorkflowStatus.RESEARCH_MUNICIPALITY.value}")
    request_id = context.request_id
    jurisdiction_ocdid = context.data.jurisdiction_ocdid
    municipality_name = context.data.config.name
    
    MAX_ATTEMPTS = 3 # Tool call + JSON output doesn't work at the same time for Google Gemini, let's retry a couple times
    for attempt in range(MAX_ATTEMPTS):
        try:
            prompt = google_gemini_prompt.research_municipality_prompt(jurisdiction_ocdid, municipality_name)
            response = await google_gemini_llm.run_prompt(
                    request_id,
                    jurisdiction_ocdid,
                    prompt,
                    response_schema=ResearchMunicipalityLLMSchema,
                    with_search=True
                )
            if not response:
                raise ValueError("No response from LLM")
            people = response.get("people", [])
            roles_found = [p.get("roles", None) for p in people if p.get("roles")]
            roles_found = [role for person_roles in roles_found for role in person_roles]

            role_configs = config_utils.get_role_configs()
            researched_people: List[ResearchedPerson] = [ResearchedPerson.model_validate(p) if isinstance(p, dict) else p for p in people]
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed with error: {e}")
            if attempt == MAX_ATTEMPTS - 1:
                raise e
            continue
    if not researched_people:
        raise RuntimeError(f"No people found for jurisdiction {jurisdiction_ocdid} after {MAX_ATTEMPTS} attempts.")

    target_people = people_utils.filter_people_by_roles(role_configs, researched_people)

    result = ResearchMunicipalityStep(
        people=people,
        elected_officials=target_people,
        notes=response.get("notes"),
    )

    return result

def normalize_role(role: str) -> str:
    """
    Normalize a role by lowercasing and handling aliases.
    """
    role = role.lower().strip()
    return role