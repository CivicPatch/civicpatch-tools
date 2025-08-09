import os
import copy
from schemas import PipelineContext, Link, LinkStatus, PipelineStatus
from utils.data_utils import MunicipalityContext
import utils.data_path_utils as data_path_utils
from typing import List, Any, Dict
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import utils.data_utils as data_utils

LLMS = [
    {
        "name": "google_gemini",
        "service": google_gemini_llm,
        "prompt": google_gemini_prompt,
    },
    #{
    #    "name": "openai",
    #}
]

def process_page_content(context: PipelineContext, page_to_process: Link):
    """
    Process the preprocessed data to extract relevant information.
    """
    print(f"Step 5: {PipelineStatus.PROCESS_PAGE_CONTENT.value}")
    # Example: Print the data or perform some processing
    # This is a placeholder for actual processing logic

    # TODO: do work to actually call LLM, figure out if there's more data here...
    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]
    people_hint = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["elected_officials"]

    cache_path = data_path_utils.get_cache_path(context["state"], context["geoid"])
    content_file_path = os.path.join(cache_path, page_to_process["folder_name"], "preprocessed.md")
    with open(content_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    municipality_context = data_utils.get_municipality_context(context["state"], context["geoid"])
    responses = process_with_llms(municipality_context, government_type, content, people_hint)

    # TODO: if there is no response, do not bump the progress
    updated_processed_data = copy.deepcopy(context["steps"][PipelineStatus.PROCESS_PAGE_CONTENT.value])
    updated_processed_data = update_data(updated_processed_data, responses)

    updated_progress = context["progress"].copy()
    updated_progress["current_data"] += 1  # Increment the count of processed data

    updated_links = []
    for link in context["links"]:
        if link["url"] == page_to_process["url"]:
            # Update the status/content for this link
            updated_links.append({**link, "status": LinkStatus.DONE.value})
        else:
            updated_links.append(link)  
    return {
        "links": updated_links,
        "progress": updated_progress,
        "steps": {
            **context["steps"],
            PipelineStatus.PROCESS_PAGE_CONTENT.value: updated_processed_data
        }
    }

def update_data(responses: Dict[str, Any], current_responses: List[Any]):
    """
    Update the data with the new responses.
    """
    updated_responses = copy.deepcopy(responses)
    # Check if the current responses already exist in the updated responses
    # If not, add them  
    for current_response in current_responses:
        llm_name = current_response.get("name")
        if llm_name not in updated_responses.keys():
            updated_responses[llm_name] = []
        updated_responses[llm_name].append(current_response["data"])

    return updated_responses

def process_with_llms(municipality_context: MunicipalityContext, government_type: str, content: str, people_hint: List[Any]):
    """
    Run the LLM prompt to process the page content.
    """
    responses = []
    for llm in LLMS:
        prompt = llm["prompt"].municipality_officials_prompt(municipality_context, government_type, content, people_hint)
        response = llm["service"].run_prompt(municipality_context, prompt)
        responses.append({
            "name": llm["name"],
            "data": response
        })

    return responses