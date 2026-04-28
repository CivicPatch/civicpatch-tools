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
    id_utils,
)
from utils import (
    merge_utils,
    people_utils,
    designation_utils,
    log_utils
)
from typing import List, Dict, Optional, Set, Tuple, cast
import services.google_gemini.llm as google_gemini_llm
import services.google_gemini.prompts as google_gemini_prompt
import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompt
from runners.people_collector.steps.step_04_process_page_content.link_frontier import (
    add_relevant_urls,
    mark_link_as_terminating_status,
    update_links,
    has_role_and_contact_info,
    _extract_names_and_designations,
    _heuristic_url_comments,
    _config_name_suffix,
)
from runners.people_collector.steps.step_04_process_page_content.heuristics import check_page_heuristics

_relevance_llm = open_router_llm
_relevance_prompt = open_router_prompt

@dataclass
class ProcessingSetup:
    roles: List[str]
    target_role: str
    target_designations: List[str]
    known_roles: List[str]

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

MINIMUM_NUM_PEOPLE = 5


async def process_page_content(context: PeopleCollectorContext, page_to_process: Link) -> Tuple[List[Link], ProcessPageContentStep]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 5: {PipelineStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process.url}")

    assert context.data.research_municipality_step is not None, "should never happen — research_municipality_step is required before process_page_content"
    setup_data = get_setup_data(context.data.research_municipality_step, context.data.role_config)
    current_step = get_or_create_step(context)
    identities = get_identities(context)
    content = read_preprocessed_content(context.data.jurisdiction_ocdid, page_to_process)

    known_roles = context.data.research_municipality_step.known_roles

    updated_links, is_relevant = await check_page_relevance(context, page_to_process, content, known_roles)
    if not is_relevant:
        return updated_links, current_step.copy(update={"links": updated_links})

    updated_raw_records, updated_records, heuristics_passed = await run_llm_loop(
        context, page_to_process, content, known_roles, current_step, identities, logger
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
        target_role="Mayor",
        target_designations=municipality_research.target_designations,
        known_roles=municipality_research.known_roles,
    )


async def check_page_relevance(context: PeopleCollectorContext, page_to_process: Link, content: str, known_roles: list[str]) -> Tuple[List[Link], bool]:
    prompt = _relevance_prompt.relevant_page_prompt(page_to_process.url, context.data.config.name or "", known_roles)
    raw_response = await _relevance_llm.run_prompt(
        context.request_id,
        context.data.jurisdiction_ocdid,
        prompt,
        response_schema=RelevantPageResponseSchema,
        content=content
    )
    response = RelevantPageResponseSchema.model_validate(raw_response)

    updated_links = copy.deepcopy(context.data.links)
    existing_records = context.data.process_page_content_step.records_by_llm if context.data.process_page_content_step else {}
    names, designations = _extract_names_and_designations(existing_records)
    relevance_logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    if response.relevant_urls:
        updated_links = add_relevant_urls(response.relevant_urls, updated_links, page_to_process.url, names, designations + known_roles, relevance_logger)
    else:
        combined_designations = designations + known_roles
        roles = known_roles + _config_name_suffix(context.data.config.name)
        heuristic_urls = _heuristic_url_comments(content, combined_designations, roles=roles)
        if heuristic_urls:
            relevance_logger.info(f"LLM returned 0 relevant URLs — falling back to {len(heuristic_urls)} heuristic URL(s)")
            updated_links = add_relevant_urls(list(heuristic_urls.keys()), updated_links, page_to_process.url, names, combined_designations, relevance_logger, url_comments=heuristic_urls)

    if not response.is_relevant:
        updated_links = mark_link_as_terminating_status(page_to_process.url, updated_links, LinkStatus.PROCESSED_IRRELEVANT)

    return updated_links, response.is_relevant


async def run_llm_loop(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    known_roles: list[str],
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

        seed = retry_count if retry_count > 0 else None
        logger.info(f"Running LLM: {llm['name']} seed={seed}")
        llm_responses, records_found = await process_with_llm(
            page_to_process.url, context.request_id, context.data.jurisdiction_ocdid,
            content, known_roles, llm,
            seed=seed,
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
    known_roles: list[str],
    llm: dict,
    seed: Optional[int] = None,
) -> Tuple[Dict[str, List[LLMPerson]], List[LLMPerson]]:
    """
    Run a single LLM's prompt to process page content.
    Checks with_batch_api flag — batch mode is a stub for now.
    """
    if llm.get("with_batch_api", False):
        raise NotImplementedError(f"Batch API not yet implemented for LLM: {llm['name']}")

    ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    prompt = llm["prompt"].municipality_officials_prompt(known_roles, state=ocdid_parts.state, county=ocdid_parts.county)
    response = await llm["service"].run_prompt(
        request_id,
        jurisdiction_ocdid,
        prompt,
        response_schema=PeopleArrayLLMResponseSchema,
        content=content,
        seed=seed,
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
    normalized_phone = phone_utils.normalize_first_phone(record.phone) if record.phone else None
    if record.phone and normalized_phone is None:
        logger.warning(f"Failed to parse phone number: {record.phone}")

    normalized_email = email_utils.normalize_email(record.email)
    if normalized_email and not email_utils.is_valid_email(normalized_email):
        logger.warning(f"Invalid email address found: {record.email}")
        if not record.url and url_utils.is_valid_url(normalized_email):
            record.url = url_utils.format_url(normalized_email)
        normalized_email = None

    return LLMPerson(
        name=record.name,
        roles=people_utils.normalize_roles(record.roles, role_config),
        designations=designation_utils.normalize_designations(record.designations),
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

    known_roles_lower = {r.strip().lower() for r in setup_data.known_roles}
    requires_mayor = not known_roles_lower or "mayor" in known_roles_lower
    sorted_counts = sorted(llm_people_counts, reverse=True)
    return ProgressState(
        required_data=progress.required_data,
        current_data=sorted_counts[0] if sorted_counts else 0,
        has_target_role=len(target_role_found) >= 1 if requires_mayor else True,
        has_target_designations=len(target_designations_found) >= 1,
    )


def read_preprocessed_content(jurisdiction_ocdid: str, page_to_process: Link) -> str:
    """Read the preprocessed markdown content."""
    cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
    content_file_path = os.path.join(cache_path, page_to_process.folder_name, "preprocessed.md")
    with open(content_file_path, "r", encoding="utf-8") as f:
        return f.read()
