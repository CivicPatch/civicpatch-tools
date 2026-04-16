import os
import re
import copy
from dataclasses import dataclass
from runners.people_collector.schemas import (
  PeopleCollectorContext,
  Link,
  LinkStatus,
  PipelineStatus,
  LLMPerson,
  PeopleArrayLLMResponseSchema,
  RecordsByLLM,
  ProcessPageContentStep,
  ResearchMunicipalityStep,
  ProgressState,
  RelevantPageResponseSchema
)
from shared.utils import (
    config_utils,
    data_path_utils,
    phone_utils,
    email_utils,
    url_utils,
    name_utils,
)
from utils import (
    merge_utils,
    people_utils,
    log_utils
)
from typing import List, Dict, Optional, Tuple, cast
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompt

# URL patterns that are deterministic dead ends. Matched against the full URL
# before adding to the crawl frontier, so the LLM never wastes a scrape on them.
# Add new patterns here rather than trying to teach the LLM to filter them.
LINK_PATTERNS_BLACKLIST = {
    # CivicPlus
    ## Calendar — generic
    r"/calendar/\d{4}\b":              "calendar: year-indexed archive",
    r"[Cc]alendar\.aspx":              "calendar: CivicPlus calendar page",
    r"\?.*\bEID=":                     "calendar: CivicPlus event instance",
    r"\?.*\bview=list\b":              "calendar: CivicPlus list view",
    r"\?.*\bCID=":                     "calendar: CivicPlus category filter",

    r"DocumentCenter/View/":           "document: CivicPlus document viewer",
}

# URL keywords that strongly indicate a governance page. Links matching any of
# these are sorted to the top of the crawl frontier, ahead of num_references.
LINK_KEYWORDS_WHITELIST = [
    "council",
    "mayor",
    "board",
    "government",
    "commission",
    "aldermen",
    "official",
    "elected",
    "representative",
]


def _blacklist_match(url: str) -> Optional[str]:
    for pattern, comment in LINK_PATTERNS_BLACKLIST.items():
        if re.search(pattern, url):
            return comment
    return None


def _whitelist_match(url: str) -> Optional[str]:
    url_lower = url.lower()
    for kw in LINK_KEYWORDS_WHITELIST:
        if kw in url_lower:
            return kw
    return None


_relevance_llm = open_router_llm
_relevance_prompt = open_router_prompt

@dataclass
class ProcessingSetup:
    roles: List[str]
    target_role: str
    target_designations: List[str]

LLMS = [
    {
        "name": "open_router",
        "service": open_router_llm,
        "prompt": open_router_prompt,
        "with_batch_api": False,
    },
    #{
    #    "name": "google_gemini",
    #    "service": google_gemini_llm,
    #    "prompt": google_gemini_prompt,
    #    "with_batch_api": False,
    #}
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
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 5: {PipelineStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process.url}")

    assert context.data.research_municipality_step is not None, "should never happen — research_municipality_step is required before process_page_content"
    setup_data = get_setup_data(context.data.research_municipality_step, context.data.role_config)
    current_step = get_or_create_step(context)
    identities = get_identities(context)
    content = read_preprocessed_content(context.data.jurisdiction_ocdid, page_to_process)

    roles_hint = context.data.research_municipality_step.roles_hint

    updated_links, is_relevant = await check_page_relevance(context, page_to_process, content)
    if not is_relevant:
        return updated_links, current_step.copy(update={"links": updated_links})

    updated_raw_records, updated_records, heuristics_passed = await run_llm_loop(
        context, page_to_process, content, roles_hint, current_step, identities, logger
    )

    updated_progress = calculate_progress(current_step.progress, updated_records, setup_data)

    if heuristics_passed:
        updated_links = update_links(context.data.config.url, updated_links, page_to_process, logger, config_utils.get_role_names(context.data.role_config), updated_records)
    else:
        updated_links = mark_link_as_terminating_status(page_to_process.url, updated_links, LinkStatus.PROCESSED_HEURISTICS_FAIL)

    return updated_links, ProcessPageContentStep(
        progress=updated_progress,
        raw_records_by_llm=updated_raw_records,
        records_by_llm=updated_records,
    )


def get_or_create_step(context: PeopleCollectorContext) -> ProcessPageContentStep:
    assert context.data.research_municipality_step is not None, "should never happen — research_municipality_step is required before get_or_create_step"
    expected_count = context.data.research_municipality_step.expected_count
    return context.data.process_page_content_step or create_process_page_content_step(
        required_data=max(MINIMUM_NUM_PEOPLE, expected_count)
    )


def get_identities(context: PeopleCollectorContext) -> Dict:
    assert context.data.research_municipality_step is not None, "should never happen — research_municipality_step is required before get_identities"
    return context.data.research_municipality_step.identities


def create_process_page_content_step(required_data: int) -> ProcessPageContentStep:
    return ProcessPageContentStep(
        records_by_llm={
            "google_gemini": {},
            "open_router": {},
        },
        raw_records_by_llm={
            "google_gemini": {},
            "open_router": {},
        },
        progress=ProgressState(
            required_data=required_data,
            current_data=0,
            has_target_role=False,
            has_target_designations=False
        ),
    )


def get_setup_data(municipality_research: ResearchMunicipalityStep, role_config=None) -> ProcessingSetup:
    return ProcessingSetup(
        roles=config_utils.get_role_names(role_config),
        target_role="Mayor",  # TBD hardcoded
        target_designations=municipality_research.target_designations,
    )


async def check_page_relevance(context: PeopleCollectorContext, page_to_process: Link, content: str) -> Tuple[List[Link], bool]:
    prompt = _relevance_prompt.relevant_page_prompt(page_to_process.url, context.data.config.name or "")
    raw_response = await _relevance_llm.run_prompt(
        context.request_id,
        context.data.jurisdiction_ocdid,
        prompt,
        response_schema=RelevantPageResponseSchema,
        content=content
    )
    response = RelevantPageResponseSchema.model_validate(raw_response)

    updated_links = copy.deepcopy(context.data.links)
    if response.relevant_urls:
        existing_records = context.data.process_page_content_step.records_by_llm if context.data.process_page_content_step else {}
        names, designations = _extract_names_and_designations(existing_records)
        roles_hint = context.data.research_municipality_step.roles_hint if context.data.research_municipality_step else []
        relevance_logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
        updated_links = add_relevant_urls(response.relevant_urls, updated_links, page_to_process.url, names, designations + roles_hint, relevance_logger)

    if not response.is_relevant:
        updated_links = mark_link_as_terminating_status(page_to_process.url, updated_links, LinkStatus.PROCESSED_IRRELEVANT)

    return updated_links, response.is_relevant


async def run_llm_loop(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    roles_hint: list[str],
    current_step: ProcessPageContentStep,
    identities: Dict,
    logger,
) -> Tuple[RecordsByLLM, RecordsByLLM, bool]:
    updated_raw_records = current_step.raw_records_by_llm
    updated_records = current_step.records_by_llm
    llm_index = 0
    retry_count = 0
    heuristics_passed = False

    while llm_index < len(LLMS):
        llm = LLMS[llm_index]

        if llm.get("with_batch_api", False):
            llm_index += 1
            retry_count = 0
            continue

        llm_responses, records_found = await process_with_llm(
            page_to_process.url, context.request_id, context.data.jurisdiction_ocdid,
            content, roles_hint, llm,
        )
        updated_raw_records, updated_records = update_step_data(
            context.data.jurisdiction_ocdid, llm_responses, identities,
            updated_records, updated_raw_records, context.data.role_config,
        )

        if check_page_heuristics(logger, page_to_process.url, content, records_found):
            logger.info(f"Heuristics passed for LLM: {llm['name']}")
            for prev_llm in LLMS[:llm_index]:
                if not prev_llm.get("with_batch_api", False):
                    updated_raw_records = wipe_records_by_source_url(updated_raw_records, prev_llm["name"], page_to_process.url)
                    updated_records = wipe_records_by_source_url(updated_records, prev_llm["name"], page_to_process.url)
            heuristics_passed = True
            break

        if retry_count < 1:
            logger.info(f"Heuristics failed for LLM: {llm['name']}, retrying.")
            retry_count += 1
            continue

        logger.info(f"Heuristics failed after retry for LLM: {llm['name']}, advancing.")
        updated_raw_records = wipe_records_by_source_url(updated_raw_records, llm["name"], page_to_process.url)
        updated_records = wipe_records_by_source_url(updated_records, llm["name"], page_to_process.url)
        llm_index += 1
        retry_count = 0
    else:
        logger.warning(f"All LLMs failed heuristics for page: {page_to_process.url}")

    return updated_raw_records, updated_records, heuristics_passed


async def process_with_llm(
    source_url: str,
    request_id,
    jurisdiction_ocdid: str,
    content: str,
    roles_hint: list[str],
    llm: dict,
) -> Tuple[Dict[str, List[LLMPerson]], List[LLMPerson]]:
    """
    Run a single LLM's prompt to process page content.
    Checks with_batch_api flag — batch mode is a stub for now.
    """
    if llm.get("with_batch_api", False):
        raise NotImplementedError(f"Batch API not yet implemented for LLM: {llm['name']}")

    prompt = llm["prompt"].municipality_officials_prompt(roles_hint)
    response = await llm["service"].run_prompt(
        request_id,
        jurisdiction_ocdid,
        prompt,
        response_schema=PeopleArrayLLMResponseSchema,
        content=content
    )

    formatted_response = cast(PeopleArrayLLMResponseSchema, response)
    processed_people = []
    for p in formatted_response.people:
        p = p.model_dump()
        if not p.get("name") or not p["name"].strip():
            continue
        p["source_url"] = source_url
        if p["url"]:
            p["url"] = url_utils.format_url(p["url"])
        processed_people.append(LLMPerson.model_validate(p))

    return {llm["name"]: processed_people}, processed_people


def update_step_data(
    jurisdiction_ocdid: str,
    llm_responses: Dict[str, List[LLMPerson]],
    merged_identities: Dict[str, List[str]],
    existing_records_by_llm: RecordsByLLM,
    existing_raw_records_by_llm: RecordsByLLM,
    role_config=None,
) -> Tuple[RecordsByLLM, RecordsByLLM]:
    """Update and normalize all processed records functionally without mutations."""
    updated_raw_records = update_records_by_llm(merged_identities, existing_raw_records_by_llm, llm_responses)

    updated_normalized_records = copy.deepcopy(existing_records_by_llm)
    logger = log_utils.get_pipeline_run_logger(jurisdiction_ocdid)

    for llm, people_by_name in updated_raw_records.items():
        updated_normalized_records[llm] = {
            name: [normalize_record(logger, person, role_config) for person in people]
            for name, people in people_by_name.items()
        }

    return updated_raw_records, updated_normalized_records


def update_records_by_llm(
    identities: Dict[str, List[str]],
    records_by_llm: RecordsByLLM,
    current_responses: Dict[str, List[LLMPerson]]
) -> RecordsByLLM:
    updated_records_by_llm = copy.deepcopy(records_by_llm)

    for llm_name, llm_people_list in current_responses.items():
        people_by_name = updated_records_by_llm.get(llm_name, {})
        updated_records_by_llm[llm_name] = merge_utils.group_people_by_name(
            identities, people_by_name, llm_people_list
        )

    return updated_records_by_llm


def wipe_records_by_source_url(records_by_llm: RecordsByLLM, llm_name: str, source_url: str) -> RecordsByLLM:
    updated = copy.deepcopy(records_by_llm)
    people_by_name = updated.get(llm_name, {})
    filtered = {
        name: [p for p in people if p.source_url != source_url]
        for name, people in people_by_name.items()
    }
    updated[llm_name] = {k: v for k, v in filtered.items() if v}
    return updated


def normalize_record(logger, record: LLMPerson, role_config=None) -> LLMPerson:
    """Normalize roles, designations, and phone number in an LLMPerson record."""
    try:
        normalized_phone = phone_utils.normalize_phone_number(record.phone) if record.phone else None
    except Exception:
        logger.warning(f"Failed to parse phone number: {record.phone}")
        normalized_phone = None

    normalized_email = email_utils.normalize_email(record.email)
    if normalized_email and not email_utils.is_valid_email(normalized_email):
        logger.warning(f"Invalid email address found: {record.email}")
        if not record.url and url_utils.is_valid_url(normalized_email):
            record.url = url_utils.format_url(normalized_email)
        normalized_email = None

    return LLMPerson(
        name=record.name,
        roles=people_utils.normalize_roles(record.roles, role_config),
        designations=people_utils.normalize_designations(record.designations),
        phone=normalized_phone,
        email=normalized_email,
        url=record.url,
        start_date=record.start_date,
        end_date=record.end_date,
        image=record.image,
        source_url=record.source_url
    )

def calculate_progress(progress: ProgressState, records_by_llm: RecordsByLLM, setup_data: ProcessingSetup) -> ProgressState:
    llm_people_counts = []
    target_role_found = set()
    target_designations_found = set()
    num_target_designations = len(setup_data.target_designations)

    for llm, people_by_name in records_by_llm.items():
        valid_people = [p for p in people_by_name.values() if has_role_and_contact_info(setup_data.roles, p)]
        llm_people_counts.append(len(valid_people))

        all_roles = {r.strip().lower() for p_list in people_by_name.values() for p in p_list for r in p.roles}
        if setup_data.target_role and setup_data.target_role.strip().lower() in all_roles:
            target_role_found.add(llm)

        if num_target_designations == 0:
            target_designations_found.add(llm)
        else:
            people_with_designations = [
                p_list for p_list in valid_people
                if any(p.designations and any(d.strip() for d in p.designations) for p in p_list)
            ]
            if len(people_with_designations) >= num_target_designations:
                target_designations_found.add(llm)

    sorted_counts = sorted(llm_people_counts, reverse=True)
    return ProgressState(
        required_data=progress.required_data,
        current_data=sorted_counts[0] if sorted_counts else 0,
        has_target_role=len(target_role_found) >= 1,
        has_target_designations=len(target_designations_found) >= 1,
    )


def has_role_and_contact_info(roles: List[str], records: List[LLMPerson]) -> bool:
    people = [LLMPerson.model_validate(r) if not isinstance(r, LLMPerson) else r for r in records]

    contact_types = set()
    for p in people:
        for field, value in [("image", p.image), ("url", p.url), ("phone", p.phone), ("email", p.email)]:
            if value:
                contact_types.add(field)
    has_contact = any(p.phone or p.email for p in people) and len(contact_types) >= 3

    all_roles = {
        r.strip().lower()
        for p in people
        for r in (p.roles or [])
        if r and r.strip()
    }
    has_role = bool(all_roles & set(roles))

    return has_contact and has_role

def check_page_heuristics(logger, source_url: str, input_text: str, records_found: List[LLMPerson]) -> bool:
    """
    Per-page heuristics check for a single LLM's results.
    Returns True if every non-empty field (email, phone, url, role) in each LLMPerson
    is present in the input_text.
    """
    input_text_lower = input_text.lower()
    for person in records_found:
        if person.name and not _name_in_text(person.name, input_text_lower):
            logger.warning(f"Name not found in input text: {person.name} under source url: {source_url}")
            return False 
        if person.email and not _email_in_text(person.email, input_text_lower):
            logger.warning(f"Email not found in input text: {person.email} under source url: {source_url}")
            return False
        if person.phone and not _phone_in_text(person.phone, input_text):
            logger.warning(f"Phone not found in input text: {person.phone} under source url: {source_url}")
            return False
        if person.url and not url_utils.url_in_text(person.url, input_text):
            if not url_utils.same_url(person.url, source_url):
                logger.warning(f"URL not found in input text: {person.url} under source url: {source_url}")
                return False
            
        # TODO: Need to use a free model/spacy to do fuzzy matching on roles and dates
        # As needed
    return True


def _name_in_text(name: str, text_lower: str) -> bool:
    """
    Check if a name appears in text, allowing for minor formatting differences
    (e.g., "Martin Cantu Jr." vs "Martin Cantu, Jr.").
    """
    name_norm = name_utils.normalize_text_for_search(name)
    text_norm = name_utils.normalize_text_for_search(text_lower)

    if name_norm in text_norm:
        return True

    parsed = name_utils.parse_name(name)
    parts = [name_utils.normalize_text_for_search(p) for p in [parsed.first, parsed.last] if p]
    return bool(parts) and all(part in text_norm for part in parts)

def _email_in_text(email: str, text_lower: str) -> bool:
    normalized = email_utils.normalize_email(email)
    if not normalized or "@" not in normalized:
        return False
    if normalized in text_lower:
        return True
    # Strip whitespace, unescape \_, and remove all non-email characters so markdown link syntax
    # and broken mailto hrefs (e.g. [user@domain.tx](mailto:user@domain.tx) .us) collapse together
    text_clean = re.sub(r"[^a-z0-9@._+\-]", "", text_lower.replace("\\_", "_"))
    if normalized in text_clean:
        return True
    # Last resort: strip all separators from both sides so district1@ci.lamesa.tx.us
    # matches district1cilamaesatxus in text
    email_alnum = re.sub(r"[^a-z0-9]", "", normalized)
    text_alnum = re.sub(r"[^a-z0-9]", "", text_clean)
    return bool(email_alnum) and email_alnum in text_alnum


def _normalize_phone(phone: str) -> str:
    """Strip all non-digit characters."""
    return re.sub(r'\D', '', phone)

def _phone_in_text(phone: str, input_text: str) -> bool:
    """Check if the core digits of a phone number appear in the text."""
    normalized_phone = _normalize_phone(phone)
    if not normalized_phone:
        return False
    # Normalize the input text to digits sequences and check for substring match
    normalized_text = _normalize_phone(input_text)
    return normalized_phone in normalized_text


def update_links(domain, context_links: List[Link], processed_page: Link, logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[Link]:
    """Update processed page status and add new website links."""
    updated_links = mark_link_as_terminating_status(processed_page.url, context_links, LinkStatus.DONE)
    return update_website_links(logger, domain, roles, updated_links, records_by_llm)


def update_website_links(logger, domain, roles, existing_links: List[Link], records_by_llm: RecordsByLLM) -> List[Link]:
    found_websites = extract_websites_from_processed_data(logger, roles, records_by_llm)
    names, designations = _extract_names_and_designations(records_by_llm)
    return add_relevant_urls(found_websites, existing_links, domain, names, designations + roles, logger)


def extract_websites_from_processed_data(logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[str]:
    found_websites = []
    for people_by_name in records_by_llm.values():
        for person_name, person_list in people_by_name.items():
            if has_role_and_contact_info(roles, person_list):
                logger.debug(f"Skipping adding websites for person with role and contact info: {person_name}")
                continue
            for person_record in person_list:
                url = person_record.url
                if url and url not in found_websites:
                    domain = url_utils.extract_domain(url)
                    if domain and not any(ignore in domain for ignore in IGNORE_WEBSITES):
                        found_websites.append(url)
    return found_websites


def _url_contains_all_tokens(url: str, terms: List[str]) -> bool:
    """Returns True if any term's complete token set is a subset of the URL's tokens."""
    url_tokens = set(re.split(r'[^a-z0-9]', url.lower()))
    for term in terms:
        term_tokens = {t for t in re.split(r'[^a-z0-9]', name_utils.normalize_text_for_search(term)) if t}
        if term_tokens and term_tokens.issubset(url_tokens):
            return True
    return False


def _url_contains_any_token(url: str, terms: List[str], min_len: int = 4) -> bool:
    """Returns True if any significant token (len >= min_len) from any term appears in the URL."""
    url_tokens = set(re.split(r'[^a-z0-9]', url.lower()))
    for term in terms:
        significant = {t for t in re.split(r'[^a-z0-9]', name_utils.normalize_text_for_search(term)) if len(t) >= min_len}
        if significant & url_tokens:
            return True
    return False


def _extract_names_and_designations(records_by_llm: RecordsByLLM) -> Tuple[List[str], List[str]]:
    names = []
    seen_names = set()
    designations = []
    seen_designations = set()
    for people_by_name in records_by_llm.values():
        for name, person_list in people_by_name.items():
            normalized = name_utils.normalize_text_for_search(name) if name else None
            if normalized and normalized not in seen_names:
                seen_names.add(normalized)
                names.append(name)
            for person in person_list:
                for d in (person.designations or []):
                    if d and d not in seen_designations:
                        seen_designations.add(d)
                        designations.append(d)
    return names, designations


def _pending_sort_key(link: Link, names: List[str], designations: List[str]) -> tuple:
    return (
        -int(_url_contains_all_tokens(link.url, names)),
        -int(_url_contains_any_token(link.url, designations)),
        -int(_whitelist_match(link.url) is not None),
        -link.num_references,
        len(url_utils.get_path(link.url).split("/")),
    )


def _find_link(links: List[Link], url: str):
    return next((link for link in links if url_utils.same_url(link.url, url)), None)


def _sort_pending(links: List[Link], names: List[str], designations: List[str]) -> List[Link]:
    pending = [l for l in links if l.status == LinkStatus.PENDING.value]
    non_pending = [l for l in links if l.status != LinkStatus.PENDING.value]
    pending.sort(key=lambda l: _pending_sort_key(l, names, designations))
    return pending + non_pending


def add_relevant_urls(urls: List[str], existing_links: List[Link], domain: str, names: Optional[List[str]] = None, designations: Optional[List[str]] = None, logger=None) -> List[Link]:
    """Add LLM-identified relevant URLs as pending links, restricted to the same domain."""
    names = names or []
    designations = designations or []
    updated_links = copy.deepcopy(existing_links)
    for link_url in urls:
        if not url_utils.same_domain(domain, link_url):
            continue
        formatted_link_url = url_utils.format_url(link_url)
        existing_link = _find_link(updated_links, formatted_link_url)
        if existing_link:
            if existing_link.status == LinkStatus.PENDING.value:
                existing_link.num_references += 1
            continue
        blacklist_comment = _blacklist_match(formatted_link_url)
        if blacklist_comment:
            if logger:
                logger.info(f"Dropping blacklisted URL ({blacklist_comment}): {formatted_link_url}")
            continue
        whitelist_comment = _whitelist_match(formatted_link_url)
        updated_links.append(Link(
            url=formatted_link_url,
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
            comment=f"whitelisted: {whitelist_comment}" if whitelist_comment else None,
        ))
    return _sort_pending(updated_links, names, designations)

def mark_link_as_terminating_status(link_url: str, existing_links: List[Link], status: LinkStatus) -> List[Link]:
    updated_links = copy.deepcopy(existing_links)
    existing_link = next((link for link in updated_links if link.url == link_url), None)
    if existing_link:
        existing_link.status = status.value
        updated_links.append(updated_links.pop(updated_links.index(existing_link)))
    return updated_links


def read_preprocessed_content(jurisdiction_ocdid: str, page_to_process: Link) -> str:
    """Read the preprocessed markdown content."""
    cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
    content_file_path = os.path.join(cache_path, page_to_process.folder_name, "preprocessed.md")
    with open(content_file_path, "r", encoding="utf-8") as f:
        return f.read()