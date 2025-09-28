from typing import List
from schemas import PipelineContext, PipelineStatus, ResearchMunicipalityStep, ResearchedPerson
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import utils.config_utils as config_utils
import utils.people_utils as people_utils

MINIMUM_ELECTED_OFFICIALS_NUM = 5

def research_municipality(context: PipelineContext):
    """
    Research the municipality to gather necessary data for further processing.
    """
    print(f"Step 1: {PipelineStatus.RESEARCH_MUNICIPALITY.value}")

    jurisdiction_id = context["jurisdiction_id"]
    municipality_name = context["name"]
    prompt = google_gemini_prompt.research_municipality_prompt(jurisdiction_id, municipality_name)
    response = google_gemini_llm.run_prompt(jurisdiction_id, prompt, with_search=True)
    people = response.get("people", [])
    government_type = response.get("government_type", "mayor_council")

    # TODO: move this to conifg
    if government_type not in ["mayor_council", "mayor_commission", "select_board", "alderman"]:
        if government_type == "council_manager":
            government_type = "mayor_council"
        else:
            raise ValueError(f"Unsupported government type: {government_type}")

    government_types = config_utils.get_government_types() 
    role_configs = government_types[government_type].get("roles", [])
    researched_people: List[ResearchedPerson] = [ResearchedPerson.model_validate(p) if isinstance(p, dict) else p for p in people]
    target_people = people_utils.filter_people_by_roles(role_configs, researched_people)

    result = ResearchMunicipalityStep(
        government_type=government_type,
        people=people,
        elected_officials=target_people,
        notes=response.get("notes"),
    )

    return {
        "progress": {
            "required_data": max(MINIMUM_ELECTED_OFFICIALS_NUM, len(target_people)),
            "current_data": 0,  # Default current data count
        },
        "steps": {
            **context["steps"],
            PipelineStatus.RESEARCH_MUNICIPALITY.value: result.model_dump()
        }
    }
