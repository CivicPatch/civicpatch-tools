from utils.data_utils import MunicipalityContext, get_municipality_context
from schemas import PipelineContext, PipelineStatus
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

    municipality_context = get_municipality_context(context["state"], context["geoid"])
    prompt = google_gemini_prompt.research_municipality_prompt(municipality_context)
    response = google_gemini_llm.run_prompt(municipality_context, prompt, with_search=True)
    people = response.get("people", [])
    government_type = response.get("government_type", "mayor_council")

    government_types = config_utils.get_government_types() 
    role_configs = government_types[government_type].get("roles", [])
    elected_officials = people_utils.filter_people_by_roles(role_configs, people)

    return {
        "progress": {
            "required_data": max(MINIMUM_ELECTED_OFFICIALS_NUM, len(elected_officials)) - 2, # Elected officials (data units) needed
            "current_data": 0,  # Default current data count
        },
        "steps": {
            **context["steps"],
            PipelineStatus.RESEARCH_MUNICIPALITY.value: {
                "government_type": response.get("government_type"),
                "people": people,
                "elected_officials": elected_officials,
                "notes": response.get("notes"),
            }
        }
    }
