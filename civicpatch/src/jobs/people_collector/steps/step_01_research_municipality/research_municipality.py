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

            # Government type can be overridden via config
            government_type = context.data.config.government_type or response.get("government_type")

            # if not government_type:
            #     logger.info(f"Could not determine government type for jurisdiction {jurisdiction_ocdid}. Roles found: {roles_found}")
            government_types = config_utils.get_government_types().keys()
            if government_type not in government_types:
                logger.warning(f"invalid government_type: {government_type}, matching government types from roles as fallback")
                government_type = match_roles_to_government_type(roles_found, config_utils.get_government_types())
                logger.info(f"setting fallback government_type: {government_type}")

            role_configs = config_utils.get_role_configs_by_government_type(government_type)
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
        government_type=government_type,
        people=people,
        elected_officials=target_people,
        notes=response.get("notes"),
    )

    return result

def match_roles_to_government_type(roles: List[str], government_types_config: Dict) -> str | None:
    """
    Determine the government type based on the roles provided.

    Args:
        roles (List[str]): A list of roles extracted from the input.
        government_types_config (Dict): The parsed government_types.yml configuration.

    Returns:
        str: The best-matching government type, or None if no match is found.
    """
    normalized_roles = [normalize_role(role) for role in roles]
    best_match = None
    highest_score = 0

    for government_type, config in government_types_config.items():
        score = 0
        config_roles = config.get("roles", [])
        for role_entry in config_roles:
            role_name = normalize_role(role_entry["role"])
            aliases = [normalize_role(alias) for alias in role_entry.get("aliases", [])]

            # Check if the role or its aliases match any input role
            for input_role in normalized_roles:
                if input_role == role_name or input_role in aliases:
                    score += 1

        # Update the best match if this government type has a higher score
        if score > highest_score:
            highest_score = score
            best_match = government_type

    return best_match

def normalize_role(role: str) -> str:
    """
    Normalize a role by lowercasing and handling aliases.
    """
    role = role.lower().strip()
    return role