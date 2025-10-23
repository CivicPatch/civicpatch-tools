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
  OtherNamesByCanonicalName,
  ResearchMunicipalityStep,
  ResearchedPerson,
  ProgressState
)
from utils import (
    merge_utils, 
    data_path_utils, 
    config_utils, 
    url_utils, 
    people_utils,
    log_utils
)
from typing import List, Any, Dict, Tuple, cast
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import services.openai.llm as openai_llm
import services.openai.prompts as openai_prompt
import services.together_ai.llm as together_ai_llm
import services.together_ai.prompts as together_ai_prompt
import phonenumbers

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
    #{
    #    "name": "together_ai",
    #    "service": together_ai_llm,  # Placeholder for Together AI service
    #    "prompt": together_ai_prompt,  # Placeholder for Together AI prompt
    #}
]
IGNORE_WEBSITES = [
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com"
]

DEFAULT_PROCESS_PAGE_CONTENT_STEP = ProcessPageContentStep(
    records_by_llm={
        "google_gemini": {},
        "openai": {},
        #"together_ai": {}
    },
    raw_records_by_llm={
        "google_gemini": {},
        "openai": {},
        #"together_ai": {}
    }
)

def process_page_content(
    context: PipelineContext,
    page_to_process: Link
) -> Dict[str, Any]:
    """
    Process the preprocessed data to extract relevant information.
    """
    logger = log_utils.get_pipeline_logger(context.jurisdiction_id)
    logger.info(f"Step 5: {PipelineStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process.url}")

    request_id = context.request_id
    jurisdiction_id = context.jurisdiction_id
    municipality_research: ResearchMunicipalityStep = ResearchMunicipalityStep.model_validate(
        cast(ResearchMunicipalityStep, context.steps[PipelineStatus.RESEARCH_MUNICIPALITY])
    )
    government_type = municipality_research.government_type

    # Only care about collecting divisions that have geographic areas
    divisions = config_utils.get_divisions()
    divisions_with_geo = [d for d, v in divisions.items() if v.get("has_geographic_area", False)]

    people_hint: List[ResearchedPerson] = municipality_research.elected_officials

    cache_path = data_path_utils.get_cache_path(jurisdiction_id)
    content_file_path = os.path.join(cache_path, page_to_process.folder_name, "preprocessed.md")
    with open(content_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    source_url = page_to_process.url

    responses = process_with_llms(source_url, request_id, jurisdiction_id, government_type, content, people_hint)

    updated_processed_data = context.steps.get(PipelineStatus.PROCESS_PAGE_CONTENT, DEFAULT_PROCESS_PAGE_CONTENT_STEP)
    if not isinstance(updated_processed_data, ProcessPageContentStep):
        updated_processed_data = ProcessPageContentStep.model_validate(updated_processed_data)

    updated_processed_data = cast(ProcessPageContentStep, updated_processed_data)

    names: Dict[str, List[str]] = context.names
    updated_names, updated_records_by_llm = update_records_by_llm(
        names, updated_processed_data.records_by_llm, responses
    )
    updated_processed_data.raw_records_by_llm = updated_records_by_llm

    for llm, people_by_name in updated_records_by_llm.items():
        for name, people in people_by_name.items():
            normalized_people = [normalize_record(logger, person, government_type) for person in people]
            updated_processed_data.records_by_llm[llm][name] = normalized_people
            updated_processed_data.raw_records_by_llm[llm][name] = people  # Keep raw records as is

    roles = config_utils.get_roles_by_government_type(government_type)
    target_role = config_utils.get_head_of_government_role(government_type)
    target_divisions = get_target_divisions(divisions_with_geo, people_hint)

    updated_progress = calculate_progress(
        context.progress, 
        updated_processed_data.records_by_llm, 
        roles,
        target_role, 
        target_divisions
    )

    updated_links = []
    for link in context.links:
        if link.url == page_to_process.url:
            # Update the status/content for this link
            link.status = LinkStatus.DONE.value
        updated_links.append(link)

    updated_links = update_website_links(logger, roles, updated_links, updated_processed_data.records_by_llm)

    return {
        "links": updated_links,
        "progress": updated_progress,
        "names": updated_names,
        "result": updated_processed_data
    }

def normalize_record(logger, record: LLMPerson, government_type: str) -> LLMPerson:
    """
    Normalize roles and divisions in an LLMPerson record.
    """
    normalized_roles = people_utils.normalize_roles(logger, government_type, record.roles)
    normalized_divisions = people_utils.normalize_divisions(record.divisions)

    try:
        phone_number = phonenumbers.parse(record.phone_number, "US") if record.phone_number else None
        normalized_phone_number = phonenumbers.format_number(phone_number, phonenumbers.PhoneNumberFormat.NATIONAL) if phone_number and phonenumbers.is_valid_number(phone_number) else None
    except:
        normalized_phone_number = None

    return LLMPerson(
        name=record.name,
        roles=normalized_roles,
        divisions=normalized_divisions,
        phone_number=normalized_phone_number,
        email=record.email,
        website=record.website,
        start_date=record.start_date,
        end_date=record.end_date,
        image=record.image,
        source=record.source
    )

def get_target_divisions(divisions_with_geo: List[str], people_hint: List[ResearchedPerson]) -> List[str]:
    """
    Extract target divisions from people hint.
    """
    divisions = set()
    for person in people_hint:
        for division in person.divisions:
            if division and division.strip() and any(dg in division.lower() for dg in divisions_with_geo):
                divisions.add(division.strip().lower())
    return list(divisions)

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
    request_id,
    jurisdiction_id: str,
    government_type: str,
    content: str,
    people_hint: List[ResearchedPerson]
) -> Dict[str, List[LLMPerson]]:
    """
    Run the LLM prompt to process the page content.
    """
    responses: Dict[str, List[LLMPerson]] = {}
    for llm in LLMS:
        prompt = llm["prompt"].municipality_officials_prompt(government_type, people_hint)
        response = llm["service"].run_prompt(
            request_id,
            jurisdiction_id,
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
    progress: ProgressState,
    updated_records_by_llm: RecordsByLLM,
    roles: List[str],
    target_role: str,
    target_divisions: List[str]
) -> ProgressState:
    """
    Update the progress based on the processed data.
    """
    llm_people_found_lengths = []
    target_role_found_with_an_llm = set()
    divisions_found_with_an_llm = set()
    num_target_divisions = len(target_divisions)

    for llm, people_by_name in updated_records_by_llm.items():
        # Only count a person if any of their records has both a role and contact info
        valid_people = [
            person_list for person_list in people_by_name.values()
            if has_role_and_contact_info(roles, person_list)
        ]
        llm_people_found_lengths.append(len(valid_people))

        if target_role:
            # Check for target role among valid people
            all_roles = {role.strip().lower() for person_list in valid_people for person in person_list for role in person.roles}
            if target_role.strip().lower() in all_roles:
                target_role_found_with_an_llm.add(llm)
        else:
            target_role_found_with_an_llm.add(llm)

        # Count valid people with non-empty divisions
        if len(target_divisions) > 0:
            people_with_divisions = [
                person_list for person_list in valid_people
                if any(person.divisions and any(d.strip() for d in person.divisions) for person in person_list)
            ]
            if len(people_with_divisions) >= num_target_divisions:
                divisions_found_with_an_llm.add(llm)
        else:
            divisions_found_with_an_llm.add(llm)

    
    # Following are only true if at least 2 LLMs found enough data
    progress.has_target_role = len(target_role_found_with_an_llm) >= 2
    progress.has_target_divisions = len(divisions_found_with_an_llm) >= 2

    sorted_lengths = sorted(llm_people_found_lengths, reverse=True)
    if len(sorted_lengths) > 1:
        progress.current_data = sorted_lengths[1]
    else:
        progress.current_data = 0

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

def update_website_links(logger, roles, existing_links: List[Link], records_by_llm: RecordsByLLM) -> List[Link]:
    """
    Update the links with websites found in the processed data.
    """
    updated_links = copy.deepcopy(existing_links)
    found_websites = extract_websites_from_processed_data(logger, roles, records_by_llm)

    for website in found_websites:
        existing_link = next((link for link in updated_links if link.url == website), None)
        if existing_link:
            if existing_link.status == LinkStatus.PENDING.value:
                # Move link to the front if it already exists
                updated_links.remove(existing_link)
                updated_links.insert(0, existing_link)
        else:
            new_link: Link = Link(
                url=website,
                status=LinkStatus.PENDING.value,
                folder_name=url_utils.format_url_to_folder(website),
                is_profile_page=True
            )
            # Add to the front of the list
            updated_links.insert(0, new_link)

    return updated_links

def extract_websites_from_processed_data(logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[str]:
    """
    Extract website links from the processed data.
    """
    found_websites = []
    for people_by_name in records_by_llm.values():
        for person_list in people_by_name.values():  # Directly iterate over lists of LLMPerson
            # If person already has a role and contact info,
            # ignore adding more websites for the person
            if has_role_and_contact_info(
                roles, person_list
            ):
                logger.debug("Skipping adding websites for person with role and contact info")
                continue

            for person_record in person_list:
                website = person_record.website if person_record.website else None

                if website and website not in found_websites:
                    # Check if website domain is in ignore list
                    domain = url_utils.extract_domain(website)
                    if domain and not any(ignore in domain for ignore in IGNORE_WEBSITES):
                        found_websites.append(website)
    return found_websites
