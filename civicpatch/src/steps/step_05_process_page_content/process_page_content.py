import os
import copy
from schemas import (
  PipelineContext, 
  Link, 
  LinkStatus, 
  PipelineStatus, 
  LLMPerson, 
  PeopleArrayLLMResponseSchema, 
  RecordsByLLM,
  ProcessPageContentStep,
  OtherNamesByCanonicalName
)
import utils.config_utils as config_utils
from utils.data_utils import MunicipalityContext
import utils.data_path_utils as data_path_utils
import utils.url_utils as url_utils
from typing import List, Any, Dict, Tuple
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import services.openai.llm as openai_llm
import services.openai.prompts as openai_prompt
import services.together_ai.llm as together_ai_llm
import services.together_ai.prompts as together_ai_prompt
import utils.data_utils as data_utils
import steps.step_05_process_page_content.merge_utils as merge_utils
from unittest.mock import patch

LLMS = [
    {
        "name": "google_gemini",
        "service": google_gemini_llm,
        "prompt": google_gemini_prompt,
    },
    {
        "name": "openai",
        "service": openai_llm,
        "prompt": openai_prompt,
    },
    {
        "name": "together_ai",
        "service": together_ai_llm,  # Placeholder for Together AI service
        "prompt": together_ai_prompt,  # Placeholder for Together AI prompt
    }
]
IGNORE_WEBSITES = [
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com"
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
    source_url = page_to_process["url"]

    responses = process_with_llms(source_url, municipality_context, government_type, content, people_hint)

    updated_processed_data: ProcessPageContentStep = context["steps"][PipelineStatus.PROCESS_PAGE_CONTENT.value]
    if not isinstance(updated_processed_data, ProcessPageContentStep):
        updated_processed_data = ProcessPageContentStep.model_validate(updated_processed_data)

    names: Dict[str, List[str]] = context["names"]
    updated_names, updated_records_by_llm = update_records_by_llm(
        names, updated_processed_data.records_by_llm, responses
    )
    updated_processed_data.records_by_llm = updated_records_by_llm

    roles = config_utils.get_all_roles_by_government_type(government_type)
    target_role = config_utils.get_head_of_government_role(government_type)
    
    updated_progress = calculate_progress(
        context["progress"].copy(), updated_processed_data.records_by_llm, target_role, roles
    )

    updated_links = []
    for link in context["links"]:
        if link["url"] == page_to_process["url"]:
            # Update the status/content for this link
            updated_links.append({**link, "status": LinkStatus.DONE.value})
        else:
            updated_links.append(link)

    updated_links = update_website_links(updated_links, updated_processed_data.records_by_llm)

    return {
        "links": updated_links,
        "progress": updated_progress,
        "names": updated_names,
        "steps": {
            **context["steps"],
            PipelineStatus.PROCESS_PAGE_CONTENT.value: updated_processed_data.model_dump()
        }
    }

def update_records_by_llm(
    names: OtherNamesByCanonicalName,
    records_by_llm: RecordsByLLM,  # map of llm name to Dict[str, List[LLMPerson]]
    current_responses: Dict[str, List[LLMPerson]]  # map of llm name to List[LLMPerson]
) -> Tuple[OtherNamesByCanonicalName, RecordsByLLM]:
    """
    Update the data with the new responses.
    """
    updated_names = copy.deepcopy(names) if names else {}  # Handle empty names
    updated_records_by_llm = copy.deepcopy(records_by_llm)
    
    for llm_name, llm_people_list in current_responses.items():
        people_by_name = updated_records_by_llm.get(llm_name, {})  # Handle missing LLM data
        updated_names, updated_people_by_name = merge_utils.group_people_by_name(
            updated_names, people_by_name, llm_people_list
        )
        updated_records_by_llm[llm_name] = updated_people_by_name

    return updated_names, updated_records_by_llm

def process_with_llms(
    source_url: str,
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
        prompt = llm["prompt"].municipality_officials_prompt(government_type, people_hint)
        response = llm["service"].run_prompt(
            municipality_context, 
            prompt, 
            response_schema=PeopleArrayLLMResponseSchema,
            content=content
        )

        # Convert LLMPerson to ProcessedLLMPerson
        people = response.people
        processed_people = []
        for p in people:
            p = p.model_dump() 
            p["source"] = source_url # Add data source URL
            if p["website"]:
                p["website"] = url_utils.format_url(p["website"])
            processed_person = LLMPerson.model_validate(p)
            processed_people.append(processed_person)
            
        responses[llm["name"]] = processed_people

    return responses

def calculate_progress(
    progress: Dict[str, Any],
    updated_records_by_llm: RecordsByLLM,
    target_role: str,
    roles: List[str]
) -> Dict[str, Any]:
    """
    Update the progress based on the processed data.
    """
    lengths = []
    target_role_found_with_an_llm = []

    for llm, people_by_name in updated_records_by_llm.items():
        filtered = [
            p for p in people_by_name.values()
            if has_role_and_contact_info(roles, p)
        ]
        lengths.append(len(filtered))
        print(f"{llm}: {len(filtered)} people with roles and contact info")

        # Flatten the nested roles structure and check for target role
        all_roles = [
            role.strip().lower()
            for person_records in filtered
            for person in person_records
            for role in person.roles
        ]
        
        has_target_role = target_role is None or target_role.lower() in all_roles
        if has_target_role:
            target_role_found_with_an_llm.append(llm)

    # Gather count of each length
    current_progress = 0
    # Find the largest value that appears at least twice
    sorted_lengths = sorted(lengths, reverse=True)
    if len(sorted_lengths) >= 2:
        current_progress = sorted_lengths[1]
    elif sorted_lengths:
        current_progress = sorted_lengths[0]
    else:
        current_progress = 0
    progress["current_data"] = current_progress
    progress["has_target_role"] = len(target_role_found_with_an_llm) > 1
    return progress

def has_role_and_contact_info(roles: List[str], records: List[LLMPerson]) -> bool:
    """
    Return True if there is at least one record with contact info
    AND at least one record with a matching role (can be different records).
    """
    people = [LLMPerson.model_validate(r) if not isinstance(r, LLMPerson) else r for r in records]

    has_contact = any(
        bool(p.phone_number) or bool(p.email) or bool(p.website)
        for p in people
    )
    # Case-insensitive role match
    has_role = any(
        any(r and r.strip().lower() in roles for r in p.roles)
        for p in people
    )
    return has_contact and has_role

def update_website_links(existing_links: List[Link], records_by_llm: RecordsByLLM) -> List[Link]:
    """
    Update the links with websites found in the processed data.
    """
    updated_links = copy.deepcopy(existing_links)
    found_websites = extract_websites_from_processed_data(records_by_llm)

    for website in found_websites:
        existing_link = next((link for link in updated_links if link["url"] == website), None)
        if existing_link:
            if existing_link["status"] == LinkStatus.PENDING.value:
                # Move link to the front if it already exists
                updated_links.remove(existing_link)
                updated_links.insert(0, existing_link)
        else:
            new_link: Link = {
                "url": website,
                "status": LinkStatus.PENDING.value,
                "folder_name": url_utils.format_url_to_folder(website),
                "is_profile_page": True
            }
            # Add to the front of the list
            updated_links.insert(0, new_link)

    return updated_links

def extract_websites_from_processed_data(records_by_llm: RecordsByLLM) -> List[str]:
    """
    Extract website links from the processed data.
    """
    found_websites = []
    for people_by_name in records_by_llm.values():
        for person_list in people_by_name.values():  # Directly iterate over lists of LLMPerson

            for person_record in person_list:
                website = person_record.website if person_record.website else None

                if website and website not in found_websites:
                    # Check if website domain is in ignore list
                    domain = url_utils.extract_domain(website)
                    if domain and not any(ignore in domain for ignore in IGNORE_WEBSITES):
                        found_websites.append(website)
    return found_websites
