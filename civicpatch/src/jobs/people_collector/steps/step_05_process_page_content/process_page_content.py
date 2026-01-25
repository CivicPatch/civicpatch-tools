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
  ProgressState,
  RelevantPageResponseSchema
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
    research_elected_officials = getattr(
        context.data.research_municipality_step, "elected_officials", {}
    )
    research_identities = {official.name: [official.name] for official in research_elected_officials}
    identities = context.data.config.identities or research_identities

    content = read_preprocessed_content(context.data.jurisdiction_ocdid, page_to_process)

    is_relevant_page_prompt = openai_prompt.relevant_page_prompt(setup_data.people_hint)
    is_relevant_response = await openai_llm.run_prompt(
        context.request_id, 
        context.data.jurisdiction_ocdid, 
        is_relevant_page_prompt,
        response_schema=RelevantPageResponseSchema, 
        content=content)
    
    response = RelevantPageResponseSchema.model_validate(is_relevant_response)
    updated_links = copy.deepcopy(context.data.links)
    if response.related_urls:
        logger.info(f"Page relevance check found related urls: {response.related_urls}")
        updated_links = move_links_to_top(context.data.config.url, response.related_urls, updated_links)

     # If page is not relevant, mark as processed_irrelevant and return
    if not response.is_relevant:
        updated_links = mark_link_as_terminating_status(page_to_process.url, updated_links, LinkStatus.PROCESSED_IRRELEVANT)

        return ProcessPageContentStep(
            raw_records_by_llm=current_step.raw_records_by_llm,
            records_by_llm=current_step.records_by_llm,
            links=updated_links,
            progress=current_step.progress,
        )

    llm_responses = await process_with_llms(
        page_to_process.url, 
        context.request_id, 
        context.data.jurisdiction_ocdid,
        research_municipality_step.government_type,
        content,
        setup_data.people_hint
    )
    
    # Process the data functionally without mutations
    updated_raw_records, updated_records = update_step_data(
        context.data.jurisdiction_ocdid,
        research_municipality_step.government_type, 
        llm_responses, 
        identities,
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
    updated_links = update_links(context.data.config.url, updated_links, page_to_process, logger, setup_data.roles, updated_records)
    logger.info(f"links updated: {updated_links}")

    return ProcessPageContentStep(
        links=updated_links,
        progress=updated_progress,
        raw_records_by_llm=updated_raw_records,
        records_by_llm=updated_records,
    )

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
    merged_identities: Dict[str, List[str]],
    existing_records_by_llm: RecordsByLLM,
    existing_raw_records_by_llm: RecordsByLLM
) -> Tuple[RecordsByLLM, RecordsByLLM]:
    """Update and normalize all processed records functionally without mutations."""
    
    # Update records without mutation
    updated_raw_records = update_records_by_llm(
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
    
    return updated_raw_records, updated_normalized_records

def update_links(domain, context_links: List[Link], processed_page: Link, logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[Link]:
    """Update processed page status and add new website links."""
    # Mark processed page as done
    updated_links = mark_link_as_terminating_status(processed_page.url, context_links, LinkStatus.DONE)

    # Add any new website links found
    return update_website_links(logger, domain, roles, updated_links, records_by_llm)

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
    identities: Dict[str, List[str]],  # map of canonical name to list of other names
    records_by_llm: RecordsByLLM,  # map of llm name to Dict[str, List[LLMPerson]]
    current_responses: Dict[str, List[LLMPerson]]  # map of llm name to List[LLMPerson]
) -> RecordsByLLM:
    """
    Update the data with the new responses.
    """
    updated_records_by_llm = copy.deepcopy(records_by_llm)
    
    for llm_name, llm_people_list in current_responses.items():
        people_by_name = updated_records_by_llm.get(llm_name, {})  # Handle missing LLM data
        updated_people_by_name = merge_utils.group_people_by_name(
            identities, people_by_name, llm_people_list
        )
        updated_records_by_llm[llm_name] = updated_people_by_name

    return updated_records_by_llm

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
    Return True if there is at least one record with a matching role
    AND at least two different types of contact info (phone, email, or URL).
    """
    people = [LLMPerson.model_validate(r) if not isinstance(r, LLMPerson) else r for r in records]

    # Collect unique types of contact info across all records
    contact_info_types = set()
    for person in people:
        if person.phone:
            contact_info_types.add("phone")
        if person.email:
            contact_info_types.add("email")
        if person.url:
            contact_info_types.add("url")
        if person.image:
            contact_info_types.add("image")

    # Check if there are at least 3 different types of contact info
    has_contact = len(contact_info_types) >= 3

    # Case-insensitive role match
    has_role = any(
        any(r and r.strip().lower() in roles for r in p.roles)
        for p in people
    )

    return has_contact and has_role

# TODO: refactor, too many params & dupe logic
def update_website_links(logger, domain, roles, existing_links: List[Link], records_by_llm: RecordsByLLM) -> List[Link]:
    """
    Update the links with websites found in the processed data.
    """
    found_websites = extract_websites_from_processed_data(logger, roles, records_by_llm)

    # Combine found websites with related URLs from relevance check
    urls = list(set(found_websites))
    return move_links_to_top(domain, urls, existing_links)

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

def move_links_to_top(domain: str, urls: List[str], existing_links: List[Link]) -> List[Link]:
    """
    Bump specified links to the top of the existing links list, under links with status PENDING 
   
    If they do not exist, add them to the top as new links.
    """
    updated_links = copy.deepcopy(existing_links)
    for link_url in urls:
        within_domain = url_utils.same_domain(domain, link_url)
        if not within_domain:
            continue
        formatted_link_url = url_utils.format_url(link_url)
        existing_link = next((link for link in updated_links if link.url == formatted_link_url), None)
        if existing_link:
            # Remove and re-insert at top (after any PENDING links)
            updated_links.remove(existing_link)
            # Find the index after the last PENDING link
            insert_index = next((i for i, link in enumerate(updated_links) if link.status != LinkStatus.PENDING.value), len(updated_links))
            updated_links.insert(insert_index, existing_link)
        else:
            # Add new link at top (after any PENDING links)
            new_link: Link = Link(
                url=formatted_link_url,
                status=LinkStatus.PENDING.value,
                folder_name="",
                is_profile_page=True
            )
            insert_index = next((i for i, link in enumerate(updated_links) if link.status != LinkStatus.PENDING.value), len(updated_links))
            updated_links.insert(insert_index, new_link)

    return updated_links

def mark_link_as_terminating_status(link_url: str, existing_links: List[Link], status: LinkStatus) -> List[Link]:
    """
    Mark the specified link as status and move it to the bottom of the list.
    """
    updated_links = copy.deepcopy(existing_links)
    existing_link = next((link for link in updated_links if link.url == link_url), None)
    if existing_link:
        existing_link.status = status.value
        # Move to bottom
        updated_links.append(updated_links.pop(updated_links.index(existing_link)))
    return updated_links