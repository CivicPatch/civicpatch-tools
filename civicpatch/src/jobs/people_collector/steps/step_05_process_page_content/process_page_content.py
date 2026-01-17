import os
import copy
from dataclasses import dataclass
from jobs.people_collector.schemas import (
  PeopleCollectorContext, 
  Link, 
  LinkStatus, 
  WorkflowStatus, 
  LLMPerson, 
  PeopleArrayLLMResponseSchema, 
  RecordsByLLM,
  ProcessPageContentStep,
  OtherNamesByCanonicalName,
  ResearchMunicipalityStep,
  ResearchedPerson,
  ProgressState
)
from shared.utils import config_utils, data_path_utils
from utils import (
    merge_utils, 
    url_utils, 
    people_utils,
    log_utils
)
from typing import List, Any, Dict, Tuple, cast, Optional
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import services.openai.llm as openai_llm
import services.openai.prompts as openai_prompt
#import services.together_ai.llm as together_ai_llm
#import services.together_ai.prompts as together_ai_prompt
import phonenumbers

@dataclass
class ProcessingSetup:
    people_hint: List[ResearchedPerson]
    roles: List[str]
    target_role: str
    target_divisions: List[str]

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
    "faceboo.com",
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

async def process_page_content(context: PeopleCollectorContext, page_to_process: Link) -> ProcessPageContentStep:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 5: {WorkflowStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process.url}")

    research_municipality_step = context.data.research_municipality_step
    setup_data = get_setup_data(research_municipality_step)
    
    # Get current step identities and merge with config
    current_step = context.data.process_page_content_step or DEFAULT_PROCESS_PAGE_CONTENT_STEP
    merged_identities = merge_config_into_names(context.data.identities, current_step.identities)
    
    content = read_preprocessed_content(context.data.jurisdiction_ocdid, page_to_process)
    llm_responses = await process_with_llms(
        page_to_process.url, 
        context.request_id, 
        context.data.jurisdiction_ocdid,
        research_municipality_step.government_type,
        content,
        setup_data.people_hint
    )
    
    # Process the data functionally without mutations
    updated_identities, updated_raw_records, updated_records = update_step_data(
        context.data.jurisdiction_ocdid,
        research_municipality_step.government_type, 
        llm_responses, 
        merged_identities,
        current_step.records_by_llm,
        current_step.raw_records_by_llm
    )
    
    updated_progress = calculate_progress(
        context.data.progress,
        updated_records,
        setup_data.roles,
        setup_data.target_role,
        setup_data.target_divisions
    )
    updated_links = update_links(context.data.links, page_to_process, logger, setup_data.roles, updated_records)
    
    return ProcessPageContentStep(
        raw_records_by_llm=updated_raw_records,
        records_by_llm=updated_records,
        links=updated_links,
        progress=updated_progress,
        identities=updated_identities
    )

def merge_config_into_names(config_identities: Optional[OtherNamesByCanonicalName], runtime_identities: Optional[OtherNamesByCanonicalName]) -> OtherNamesByCanonicalName:
    """
    Merge config-based identity mappings with runtime identities.
    Config takes priority - if there's a conflict, config wins.
    """
    # Start with config (priority)
    merged_identities = copy.deepcopy(config_identities) if config_identities else {}
    
    # Add runtime discoveries that don't conflict with config
    for canonical, variants in (runtime_identities or {}).items():
        # Check if this canonical name conflicts with any config mapping
        canonical_in_config = any(
            canonical.lower().strip() == config_canonical.lower().strip() or
            canonical.lower().strip() in [v.lower().strip() for v in config_variants]
            for config_canonical, config_variants in (config_identities or {}).items()
        )
        
        if not canonical_in_config:
            # No conflict - add the runtime mapping
            merged_identities[canonical] = variants
        else:
            # There's a conflict - config wins, but log it
            logger = log_utils.get_workflow_logger("system")
            logger.info(f"Config identity mapping overriding runtime discovery for: {canonical}")
    
    return merged_identities

def get_setup_data(municipality_research: ResearchMunicipalityStep) -> ProcessingSetup: 
    divisions = config_utils.get_divisions()
    divisions_with_geo = [d for d, v in divisions.items() if v.get("has_geographic_area", False)]
    
    roles = config_utils.get_roles_by_government_type(municipality_research.government_type)
    target_role = config_utils.get_head_of_government_role(municipality_research.government_type)
    target_divisions = get_target_divisions(divisions_with_geo, municipality_research.elected_officials)
    
    return ProcessingSetup(
        people_hint=municipality_research.elected_officials,
        roles=roles,
        target_role=target_role,
        target_divisions=target_divisions
    )


def read_preprocessed_content(jurisdiction_ocdid: str, page_to_process: Link) -> str:
    """Read the preprocessed markdown content."""
    cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
    content_file_path = os.path.join(cache_path, page_to_process.folder_name, "preprocessed.md")
    
    with open(content_file_path, "r", encoding="utf-8") as f:
        return f.read()


def update_step_data(
    jurisdiction_ocdid: str,
    government_type: str, 
    llm_responses: Dict[str, List[LLMPerson]], 
    merged_identities: OtherNamesByCanonicalName,
    existing_records_by_llm: RecordsByLLM,
    existing_raw_records_by_llm: RecordsByLLM
) -> tuple[OtherNamesByCanonicalName, RecordsByLLM, RecordsByLLM]:
    """Update and normalize all processed records functionally without mutations."""
    
    # Update records without mutation
    updated_identities, updated_raw_records = update_records_by_llm(
        merged_identities,
        existing_records_by_llm, 
        llm_responses
    )
    
    # Create normalized records from raw records
    updated_normalized_records = copy.deepcopy(existing_records_by_llm)
    logger = log_utils.get_workflow_logger(jurisdiction_ocdid)
    
    for llm, people_by_name in updated_raw_records.items():
        updated_normalized_records[llm] = {}
        for name, people in people_by_name.items():
            normalized_people = [normalize_record(logger, person, government_type) for person in people]
            updated_normalized_records[llm][name] = normalized_people
    
    return updated_identities, updated_raw_records, updated_normalized_records

def update_links(context_links: List[Link], processed_page: Link, logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[Link]:
    """Update processed page status and add new website links."""
    # Mark processed page as done
    updated_links = []
    for link in context_links:
        if link.url == processed_page.url:
            link.status = LinkStatus.DONE.value
        updated_links.append(link)
    
    # Add any new website links found
    return update_website_links(logger, roles, updated_links, records_by_llm)

def normalize_record(logger, record: LLMPerson, government_type: str) -> LLMPerson:
    """
    Normalize roles and divisions in an LLMPerson record.
    """
    normalized_roles = people_utils.normalize_roles(logger, government_type, record.roles)
    normalized_divisions = people_utils.normalize_divisions(record.divisions)

    try:
        phone = phonenumbers.parse(record.phone, "US") if record.phone else None
        normalized_phone = phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.NATIONAL) if phone and phonenumbers.is_valid_number(phone) else None
    except:
        logger.warning(f"Failed to parse phone number: {record.phone}")
        normalized_phone = None

    return LLMPerson(
        name=record.name,
        roles=normalized_roles,
        divisions=normalized_divisions,
        phone=normalized_phone,
        email=record.email,
        url=record.url,
        start_date=record.start_date,
        end_date=record.end_date,
        image=record.image,
        source_url=record.source_url
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
    identities: OtherNamesByCanonicalName,
    records_by_llm: RecordsByLLM,  # map of llm name to Dict[str, List[LLMPerson]]
    current_responses: Dict[str, List[LLMPerson]]  # map of llm name to List[LLMPerson]
) -> Tuple[OtherNamesByCanonicalName, RecordsByLLM]:
    """
    Update the data with the new responses.
    """
    updated_identities = copy.deepcopy(identities) if identities else {}  # Handle empty identities
    updated_records_by_llm = copy.deepcopy(records_by_llm)
    
    for llm_name, llm_people_list in current_responses.items():
        people_by_name = updated_records_by_llm.get(llm_name, {})  # Handle missing LLM data
        updated_identities, updated_people_by_name = merge_utils.group_people_by_name(
            updated_identities, people_by_name, llm_people_list
        )
        updated_records_by_llm[llm_name] = updated_people_by_name

    return updated_identities, updated_records_by_llm

async def process_with_llms(
    source_url: str,
    request_id,
    jurisdiction_ocdid: str,
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
        response = await llm["service"].run_prompt(
            request_id,
            jurisdiction_ocdid,
            prompt,
            response_schema=PeopleArrayLLMResponseSchema,
            content=content
        )

        # Convert RawLLMPerson to LLMPerson
        formatted_response = cast(PeopleArrayLLMResponseSchema, response)
        people = formatted_response.people
        processed_people = []
        for p in people:
            p = p.model_dump() 
            p["source_url"] = source_url # Add data source URL
            if p["url"]:
                p["url"] = url_utils.format_url(p["url"])
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

    has_contact = (
        sum(bool(p.phone) for p in people) +
        sum(bool(p.email) for p in people) +
        sum(bool(p.url) for p in people)
    ) >= 3
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
            # Only update if status is PENDING - don't re-add to list
            if existing_link.status == LinkStatus.PENDING.value:
                updated_links.remove(existing_link)
                existing_link.is_profile_page = True
                updated_links.insert(0, existing_link)
        else:
            # Only add if it's a completely new link
            new_link: Link = Link(
                url=website,
                status=LinkStatus.PENDING.value,
                folder_name=url_utils.format_url_to_folder(website),
                is_profile_page=True
            )
            updated_links.insert(0, new_link)

    return updated_links

def extract_websites_from_processed_data(logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[str]:
    """
    Extract website links from the processed data.
    """
    found_websites = []
    # For each llm source
    for people_by_name in records_by_llm.values():
        # For each person identity
        for person_name, person_list in people_by_name.items():
            # If person already has a role and contact info,
            # ignore adding more websites for the person
            if has_role_and_contact_info(
                roles, person_list
            ):
                logger.debug(f"Skipping adding websites for person with role and contact info: {person_name}")
                continue

            for person_record in person_list:
                url = person_record.url if person_record.url else None

                if url and url not in found_websites:
                    # Check if url domain is in ignore list
                    domain = url_utils.extract_domain(url)
                    if domain and not any(ignore in domain for ignore in IGNORE_WEBSITES):
                        found_websites.append(url)
    return found_websites
