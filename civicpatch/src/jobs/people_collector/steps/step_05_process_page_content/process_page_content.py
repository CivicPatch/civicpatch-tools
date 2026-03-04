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
  ResearchMunicipalityStep,
  ResearchedPerson,
  ProgressState,
  RelevantPageResponseSchema
)
from shared.utils import (
    config_utils, 
    data_path_utils, 
    phone_utils
)
from utils import (
    merge_utils, 
    url_utils, 
    people_utils,
    log_utils
)
from typing import List, Dict, Tuple, cast 
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import services.together_ai.llm as together_ai_llm
import services.together_ai.prompts as together_ai_prompt

@dataclass
class ProcessingSetup:
    people_hint: List[ResearchedPerson]
    roles: List[str]
    target_role: str
    target_designations: List[str]

LLMS = [
    {
        "name": "together_ai",
        "service": together_ai_llm,
        "prompt": together_ai_prompt,
        "with_batch_api": False,
    },
    {
        "name": "google_gemini",
        "service": google_gemini_llm,
        "prompt": google_gemini_prompt,
        "with_batch_api": False,
    }
]

IGNORE_WEBSITES = [
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com"
]

MINIMUM_NUM_PEOPLE = 5


async def process_page_content(context: PeopleCollectorContext, page_to_process: Link) -> Tuple[List[Link], ProcessPageContentStep]:
    logger = log_utils.get_workflow_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 5: {WorkflowStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process.url}")

    research_municipality_step = context.data.research_municipality_step
    setup_data = get_setup_data(research_municipality_step)
    research_elected_officials = research_municipality_step.elected_officials

    default_current_step = create_process_page_content_step(
        required_data=max(MINIMUM_NUM_PEOPLE, len(research_elected_officials))
    )
    current_step = context.data.process_page_content_step or default_current_step
    research_identities = {official.name: [official.name] for official in research_elected_officials}
    identities = context.data.config.identities or research_identities

    content = read_preprocessed_content(context.data.jurisdiction_ocdid, page_to_process)

    is_relevant_page_prompt = together_ai_prompt.relevant_page_prompt(
        page_to_process.url
    )
    is_relevant_response = await together_ai_llm.run_prompt(
        context.request_id, 
        context.data.jurisdiction_ocdid, 
        is_relevant_page_prompt,
        response_schema=RelevantPageResponseSchema, 
        content=content
    )

    response = RelevantPageResponseSchema.model_validate(is_relevant_response)
    updated_links = copy.deepcopy(context.data.links)
    if response.relevant_urls:
        logger.info(f"Page relevance check found related urls: {response.relevant_urls}")
        updated_links = move_links_to_top(context.data.config.url, response.relevant_urls, updated_links)

    # If page is not relevant, mark as processed_irrelevant and return
    if not response.is_relevant:
        updated_links = mark_link_as_terminating_status(page_to_process.url, updated_links, LinkStatus.PROCESSED_IRRELEVANT)

        return updated_links, ProcessPageContentStep(
            raw_records_by_llm=current_step.raw_records_by_llm,
            records_by_llm=current_step.records_by_llm,
            links=updated_links,
            progress=current_step.progress,
            current_llm_index=current_step.current_llm_index,
        )

    # Per-page LLM retry loop:
    # For each sequential LLM, run once, check heuristics, retry once if fail, then advance to next LLM.
    # Batch LLMs are skipped here — they are handled at the pipeline level.
    current_llm_index = current_step.current_llm_index
    current_llm_retry_count = current_step.current_llm_retry_count
    updated_raw_records = current_step.raw_records_by_llm
    updated_records = current_step.records_by_llm

    while current_llm_index < len(LLMS):
        current_llm = LLMS[current_llm_index]

        if current_llm.get("with_batch_api", False):
            current_llm_index += 1
            current_llm_retry_count = 0
            continue

        llm_responses, records_found = await process_with_llm(
            page_to_process.url,
            context.request_id,
            context.data.jurisdiction_ocdid,
            content,
            setup_data.people_hint,
            current_llm,
        )

        updated_raw_records, updated_records = update_step_data(
            context.data.jurisdiction_ocdid,
            llm_responses,
            identities,
            updated_records,
            updated_raw_records,
        )


        page_heuristics_pass = check_page_heuristics(logger, content, records_found)

        if page_heuristics_pass:
            logger.info(f"Per-page heuristics passed for LLM: {current_llm['name']}")
            # Clear records from any previously failed LLMs
            for prev_llm in LLMS[:current_llm_index]:
                if not prev_llm.get("with_batch_api", False):
                    updated_raw_records[prev_llm["name"]] = {}
                    updated_records[prev_llm["name"]] = {}
            break
        elif current_llm_retry_count < 1:
            logger.info(f"Per-page heuristics failed for LLM: {current_llm['name']}, retrying once.")
            current_llm_retry_count += 1
        else:
            logger.info(f"Per-page heuristics failed after retry for LLM: {current_llm['name']}, advancing to next LLM.")
            # Clear failed LLM's records — if next LLM also fails, it becomes the best-effort fallback
            updated_raw_records[current_llm["name"]] = {}
            updated_records[current_llm["name"]] = {}
            current_llm_index += 1
            current_llm_retry_count = 0

    updated_progress = calculate_progress(
        current_step.progress,
        updated_records,
        setup_data.roles,
        setup_data.target_role,
        setup_data.target_designations
    )
    updated_links = update_links(context.data.config.url, updated_links, page_to_process, logger, setup_data.roles, updated_records)
    logger.info(f"links updated: {updated_links}")

    return updated_links, ProcessPageContentStep(
        progress=updated_progress,
        raw_records_by_llm=updated_raw_records,
        records_by_llm=updated_records,
        current_llm_index=current_llm_index,
        current_llm_retry_count=current_llm_retry_count,
    )


def create_process_page_content_step(
        required_data: int
        ) -> ProcessPageContentStep:
    return ProcessPageContentStep(
        records_by_llm={
            "google_gemini": {},
            "together_ai": {},
        },
        raw_records_by_llm={
            "google_gemini": {},
            "together_ai": {},
        },
        links=[],
        progress=ProgressState(
            required_data=required_data,
            current_data=0,
            has_target_role=False,
            has_target_designations=False
        ),
        current_llm_index=0,
        current_llm_retry_count=0,
    )


def get_setup_data(municipality_research: ResearchMunicipalityStep) -> ProcessingSetup: 
    designations = config_utils.get_designations()
    designations_with_geo = [d for d, v in designations.items() if v.get("has_geographic_area", False)]
    
    roles = config_utils.get_role_names()
    target_role = "Mayor"  # TBD hardcoded
    target_designations = get_target_designations(designations_with_geo, municipality_research.elected_officials)

    return ProcessingSetup(
        people_hint=municipality_research.elected_officials,
        roles=roles,
        target_role=target_role,
        target_designations=target_designations
    )


def read_preprocessed_content(jurisdiction_ocdid: str, page_to_process: Link) -> str:
    """Read the preprocessed markdown content."""
    cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
    content_file_path = os.path.join(cache_path, page_to_process.folder_name, "preprocessed.md")
    
    with open(content_file_path, "r", encoding="utf-8") as f:
        return f.read()


def update_step_data(
    jurisdiction_ocdid: str,
    llm_responses: Dict[str, List[LLMPerson]], 
    merged_identities: Dict[str, List[str]],
    existing_records_by_llm: RecordsByLLM,
    existing_raw_records_by_llm: RecordsByLLM
) -> Tuple[RecordsByLLM, RecordsByLLM]:
    """Update and normalize all processed records functionally without mutations."""
    updated_raw_records = update_records_by_llm(
        merged_identities,
        existing_raw_records_by_llm,
        llm_responses
    )
    
    updated_normalized_records = copy.deepcopy(existing_records_by_llm)
    logger = log_utils.get_workflow_logger(jurisdiction_ocdid)
    
    for llm, people_by_name in updated_raw_records.items():
        updated_normalized_records[llm] = {}
        for name, people in people_by_name.items():
            normalized_people = [normalize_record(logger, person) for person in people]
            updated_normalized_records[llm][name] = normalized_people
    
    return updated_raw_records, updated_normalized_records


def update_links(domain, context_links: List[Link], processed_page: Link, logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[Link]:
    """Update processed page status and add new website links."""
    updated_links = mark_link_as_terminating_status(processed_page.url, context_links, LinkStatus.DONE)
    return update_website_links(logger, domain, roles, updated_links, records_by_llm)


def normalize_record(logger, record: LLMPerson) -> LLMPerson:
    """Normalize roles and designations in an LLMPerson record."""
    normalized_roles = people_utils.normalize_roles(record.roles)
    normalized_designations = people_utils.normalize_designations(record.designations)

    try:
        normalized_phone = phone_utils.normalize_phone_number(record.phone) if record.phone else None
    except:
        logger.warning(f"Failed to parse phone number: {record.phone}")
        normalized_phone = None

    return LLMPerson(
        name=record.name,
        roles=normalized_roles,
        designations=normalized_designations,
        phone=normalized_phone,
        email=record.email,
        url=record.url,
        start_date=record.start_date,
        end_date=record.end_date,
        image=record.image,
        source_url=record.source_url
    )


def get_target_designations(designations_with_geo: List[str], people_hint: List[ResearchedPerson]) -> List[str]:
    designations = set()
    for person in people_hint:
        for designation in person.designations:
            if designation and designation.strip() and any(dg in designation.lower() for dg in designations_with_geo):
                designations.add(designation.strip().lower())
    return list(designations)


def update_records_by_llm(
    identities: Dict[str, List[str]],
    records_by_llm: RecordsByLLM,
    current_responses: Dict[str, List[LLMPerson]]
) -> RecordsByLLM:
    updated_records_by_llm = copy.deepcopy(records_by_llm)
    
    for llm_name, llm_people_list in current_responses.items():
        people_by_name = updated_records_by_llm.get(llm_name, {})
        updated_people_by_name = merge_utils.group_people_by_name(
            identities, people_by_name, llm_people_list
        )
        updated_records_by_llm[llm_name] = updated_people_by_name

    return updated_records_by_llm


async def process_with_llm(
    source_url: str,
    request_id,
    jurisdiction_ocdid: str,
    content: str,
    people_hint: List[ResearchedPerson],
    llm: dict,
) -> Tuple[Dict[str, List[LLMPerson]], List[LLMPerson]]:
    """
    Run a single LLM's prompt to process page content.
    Checks with_batch_api flag — batch mode is a stub for now.
    """
    responses: Dict[str, List[LLMPerson]] = {}

    if llm.get("with_batch_api", False):
        # TODO: implement batch API submission
        raise NotImplementedError(f"Batch API not yet implemented for LLM: {llm['name']}")

    prompt = llm["prompt"].municipality_officials_prompt(people_hint)
    response = await llm["service"].run_prompt(
        request_id,
        jurisdiction_ocdid,
        prompt,
        response_schema=PeopleArrayLLMResponseSchema,
        content=content
    )

    formatted_response = cast(PeopleArrayLLMResponseSchema, response)
    people = formatted_response.people
    processed_people = []
    for p in people:
        p = p.model_dump()
        p["source_url"] = source_url
        if p["url"]:
            p["url"] = url_utils.format_url(p["url"])
        processed_person = LLMPerson.model_validate(p)
        processed_people.append(processed_person)

    responses[llm["name"]] = processed_people
    return responses, processed_people


def check_page_heuristics(logger, input_text: str, records_found: List[LLMPerson]) -> bool:
    """
    Per-page heuristics check for a single LLM's results.
    Returns True if every non-empty field (email, phone, url, role) in each LLMPerson
    is present in the input_text.
    """
    input_text_lower = input_text.lower()
    for person in records_found:
        # Check email
        if person.email and person.email.lower() not in input_text_lower:
            logger.warning(f"Email not found in input text: {person.email}")
            return False
        # Check phone
        if person.phone and person.phone not in input_text:
            logger.warning(f"Phone not found in input text: {person.phone}")
            return False
        # Check url
        if person.url and person.url not in input_text:
            logger.warning(f"URL not found in input text: {person.url}")
            return False
        # Check roles
        if person.roles:
            for role in person.roles:
                if role and role.lower() not in input_text_lower:
                    logger.warning(f"Role not found in input text: {role}")
                    return False
    return True


def check_pipeline_heuristics(records_by_llm: RecordsByLLM, progress: ProgressState) -> bool:
    """
    Pipeline-level heuristics check run after all pages are processed.
    Returns True if overall quality is acceptable, False triggers pipeline failure.
    TODO: implement real heuristics, e.g.:
      - minimum total people found across all LLMs
      - target role present in at least one LLM's results
      - sufficient contact info coverage
    """
    return True


def calculate_progress(
    progress: ProgressState,
    updated_records_by_llm: RecordsByLLM,
    roles: List[str],
    target_role: str,
    target_designations: List[str]
) -> ProgressState:
    llm_people_found_lengths = []
    target_role_found_with_an_llm = set()
    designations_found_with_an_llm = set()
    num_target_designations = len(target_designations)

    for llm, people_by_name in updated_records_by_llm.items():
        valid_people = [
            person_list for person_list in people_by_name.values()
            if has_role_and_contact_info(roles, person_list)
        ]
        llm_people_found_lengths.append(len(valid_people))

        if target_role:
            all_roles = {role.strip().lower() for person_list in valid_people for person in person_list for role in person.roles}
            if target_role.strip().lower() in all_roles:
                target_role_found_with_an_llm.add(llm)
        else:
            target_role_found_with_an_llm.add(llm)

        if len(target_designations) > 0:
            people_with_designations = [
                person_list for person_list in valid_people
                if any(person.designations and any(d.strip() for d in person.designations) for person in person_list)
            ]
            if len(people_with_designations) >= num_target_designations:
                designations_found_with_an_llm.add(llm)
        else:
            designations_found_with_an_llm.add(llm)

    required_llm_count = 1
    progress.has_target_role = len(target_role_found_with_an_llm) >= required_llm_count
    progress.has_target_designations = len(designations_found_with_an_llm) >= required_llm_count

    sorted_lengths = sorted(llm_people_found_lengths, reverse=True)
    if len(sorted_lengths) >= required_llm_count:
        progress.current_data = sorted_lengths[required_llm_count - 1]
    else:
        progress.current_data = 0

    return progress


def has_role_and_contact_info(roles: List[str], records: List[LLMPerson]) -> bool:
    people = [LLMPerson.model_validate(r) if not isinstance(r, LLMPerson) else r for r in records]

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

    has_contact = len(contact_info_types) >= 3

    has_role = any(
        any(r and r.strip().lower() in roles for r in p.roles)
        for p in people
    )

    return has_contact and has_role


def update_website_links(logger, domain, roles, existing_links: List[Link], records_by_llm: RecordsByLLM) -> List[Link]:
    found_websites = extract_websites_from_processed_data(logger, roles, records_by_llm)
    urls = list(set(found_websites))
    return move_links_to_top(domain, urls, existing_links)


def extract_websites_from_processed_data(logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[str]:
    found_websites = []
    for people_by_name in records_by_llm.values():
        for person_name, person_list in people_by_name.items():
            if has_role_and_contact_info(roles, person_list):
                logger.debug(f"Skipping adding websites for person with role and contact info: {person_name}")
                continue

            for person_record in person_list:
                url = person_record.url if person_record.url else None

                if url and url not in found_websites:
                    domain = url_utils.extract_domain(url)
                    if domain and not any(ignore in domain for ignore in IGNORE_WEBSITES):
                        found_websites.append(url)
    return found_websites


def move_links_to_top(domain: str, urls: List[str], existing_links: List[Link]) -> List[Link]:
    updated_links = copy.deepcopy(existing_links)
    for link_url in urls:
        within_domain = url_utils.same_domain(domain, link_url)
        if not within_domain:
            continue
        formatted_link_url = url_utils.format_url(link_url)
        existing_link = next((link for link in updated_links if link.url == formatted_link_url), None)
        if existing_link:
            updated_links.remove(existing_link)
            insert_index = next((i for i, link in enumerate(updated_links) if link.status != LinkStatus.PENDING.value), len(updated_links))
            updated_links.insert(insert_index, existing_link)
        else:
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
    updated_links = copy.deepcopy(existing_links)
    existing_link = next((link for link in updated_links if link.url == link_url), None)
    if existing_link:
        existing_link.status = status.value
        updated_links.append(updated_links.pop(updated_links.index(existing_link)))
    return updated_links
