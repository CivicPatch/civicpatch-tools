import os
import copy
from schemas import (
  PipelineContext, 
  Link, 
  LinkStatus, 
  PipelineStatus, 
  LLMPerson, 
  PeopleArrayLLMResponseSchema, 
  ProcessedDataDict, 
  ProcessedLLMPeople,
  LLMResponsesDict,
  pydantic_to_dict,
  dict_to_pydantic
)
import utils.config_utils as config_utils
from utils.data_utils import MunicipalityContext
import utils.data_path_utils as data_path_utils
import utils.url_utils as url_utils
from typing import List, Any, Dict
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import services.openai.llm as openai_llm
import services.openai.prompts as openai_prompt
import utils.data_utils as data_utils
import services.google_gemini.response_schemas as gemini_response_schemas
import services.openai.response_schemas as openai_response_schemas
import steps.step_05_process_page_content.merge_utils as merge_utils

LLMS = [
    {
        "name": "google_gemini",
        "service": google_gemini_llm,
        "prompt": google_gemini_prompt,
        "response_schema": gemini_response_schemas.GEMINI_PEOPLE_ARRAY_SCHEMA
    },
    {
        "name": "openai",
        "service": openai_llm,
        "prompt": openai_prompt,
        "response_schema": openai_response_schemas.OpenAIPeopleArray
    }
]

def process_page_content(
    context: PipelineContext,
    page_to_process: Link
) -> Dict[str, Any]:
    """
    Process the preprocessed data to extract relevant information.
    """
    print(f"Step 5: {PipelineStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process['url']}")

    government_type = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["government_type"]
    people_hint = context["steps"][PipelineStatus.RESEARCH_MUNICIPALITY.value]["elected_officials"]

    cache_path = data_path_utils.get_cache_path(context["state"], context["geoid"])
    content_file_path = os.path.join(cache_path, page_to_process["folder_name"], "preprocessed.md")
    with open(content_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    municipality_context = data_utils.get_municipality_context(context["state"], context["geoid"])
    responses = process_with_llms(municipality_context, government_type, content, people_hint)

    updated_processed_data = copy.deepcopy(context["steps"][PipelineStatus.PROCESS_PAGE_CONTENT.value])
    updated_processed_data = update_data(updated_processed_data, responses)

    roles = config_utils.get_all_roles_by_government_type(government_type)
    updated_progress = update_progress(context["progress"].copy(), updated_processed_data, roles)

    updated_links = []
    for link in context["links"]:
        if link["url"] == page_to_process["url"]:
            # Update the status/content for this link
            updated_links.append({**link, "status": LinkStatus.DONE.value})
        else:
            updated_links.append(link)  

    updated_links = update_website_links(updated_links, updated_processed_data)

    return {
        "links": updated_links,
        "progress": updated_progress,
        "steps": {
            **context["steps"],
            PipelineStatus.PROCESS_PAGE_CONTENT.value: updated_processed_data
        }
    }

def update_data(
    updated_processed_data: ProcessedDataDict, # map of llm name to Dict[str, ProcessedLLMPeople]
    current_responses: LLMResponsesDict
) -> ProcessedDataDict:
    """
    Update the data with the new responses.
    """
    processed_data = copy.deepcopy(updated_processed_data)
    # Check if the current responses already exist in the updated responses
    # If not, add them  
    for llm_name, llm_people_list in current_responses.items():
        people_by_name = processed_data[llm_name]
        people_by_name = dict_to_pydantic(people_by_name, ProcessedLLMPeople)
        processed_data[llm_name] = merge_utils.group_people_by_name(people_by_name, llm_people_list)

    return pydantic_to_dict(processed_data)

def process_with_llms(
    municipality_context: MunicipalityContext,
    government_type: str,
    content: str,
    people_hint: List[Any]
) -> Dict[str, List[LLMPerson]]:
    """
    Run the LLM prompt to process the page content.
    """
    responses: Dict[str, List[LLMPerson]] = {}
    for llm in LLMS:
        prompt = llm["prompt"].municipality_officials_prompt(government_type, content, people_hint)
        response: PeopleArrayLLMResponseSchema = llm["service"].run_prompt(
            municipality_context, prompt, response_schema=PeopleArrayLLMResponseSchema
        )

        people = response["people"] if response else []
        people_llm = [LLMPerson.model_validate(p) if not isinstance(p, LLMPerson) else p for p in people]
        responses[llm["name"]] = people_llm

    return responses

def update_progress(
    progress: Dict[str, Any],
    updated_processed_data: Dict[str, Dict[str, dict]],
    roles: List[str]
) -> Dict[str, Any]:
    # For each LLM, get all ProcessedLLMPeople dicts, filter by has_contact_info, and find the shortest list
    min_length = float('inf')

    for _, people_by_name in updated_processed_data.items():
        filtered = [
            p for p in people_by_name.values()
            if has_role_and_contact_info(roles, p["records"])
        ]
        min_length = min(min_length, len(filtered))
    progress["current_data"] = min_length if min_length != float('inf') else 0
    return progress

def has_role_and_contact_info(roles: List[str], records: List[Any]) -> bool:
    """
    Return True if there is at least one record with contact info
    AND at least one record with a matching role (can be different records).
    """
    people = [LLMPerson.model_validate(r) if not isinstance(r, LLMPerson) else r for r in records]

    has_contact = any(
        (p.phone_number and p.phone_number.data) or
        (p.email and p.email.data) or
        (p.website and p.website.data)
        for p in people
    )
    # Case-insensitive role match
    roles_normalized = [role.strip().lower() for role in roles]
    has_role = any(
        any(r.data and r.data.strip().lower() in roles_normalized for r in p.roles)
        for p in people
    )
    return has_contact and has_role

def update_website_links(updated_links: List[Link], updated_processed_data: ProcessedDataDict) -> List[Link]:
    """
    Update the links with websites found in the processed data.
    """
    found_websites = extract_websites_from_processed_data(updated_processed_data)

    # Update existing links or add new ones
    for website in found_websites:
        existing_link = next((link for link in updated_links if link["url"] == website), None)
        if existing_link and existing_link["status"] == LinkStatus.PENDING.value:
            # Move link to the front if it already exists
            updated_links.remove(existing_link)
            updated_links.insert(0, existing_link)
        else:
            new_link: Link = {
                "url": website,
                "status": LinkStatus.PENDING.value,
                "folder_name": url_utils.format_url_to_folder(website)
            }
            updated_links.append(new_link)

    return updated_links

def extract_websites_from_processed_data(processed_data: ProcessedDataDict) -> List[str]:
    """
    Extract website links from the processed data.
    """
    found_websites = []
    for people_by_name in processed_data.values():
        for person in people_by_name.values():
            for record in person["records"]:
                website = record.get("website", {}).get("data")
                if website and website not in found_websites:
                    found_websites.append(website)
    return found_websites