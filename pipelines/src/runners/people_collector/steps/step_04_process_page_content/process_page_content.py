import os
import copy
from dataclasses import dataclass
from runners.people_collector.schemas import (
    PeopleCollectorContext,
    Link,
    LinkFrontier,
    LinkStatus,
    PipelineStatus,
    LLMPerson,
    PeopleArrayLLMResponseSchema,
    RecordsByLLM,
    ProcessPageContentStep,
    ProgressState,
    RelevantPageResponseSchema,
)
from shared.utils import (
    config_utils,
    data_path_utils,
    phone_utils,
    email_utils,
    url_utils,
    id_utils,
)
from utils import merge_utils, people_utils, designation_utils, log_utils
from typing import List, Dict, Optional, Tuple, cast
import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompt
from semantic_text_splitter import MarkdownSplitter
from runners.people_collector.utils.link_discovery import (
    add_relevant_urls,
    mark_link_as_terminating_status,
    update_links,
    has_role_and_contact_info,
    extract_names_and_designations,
    find_heuristic_urls,
    jurisdiction_name_suffix,
)
from runners.people_collector.steps.step_04_process_page_content.heuristics import check_page_heuristics


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
        "max_content_chars": open_router_llm.max_content_chars,
    },
]

MINIMUM_NUM_PEOPLE = 5
_CHUNK_OVERLAP_CHARS = 500


def _build_prompt(llm: dict, known_roles: list[str], jurisdiction_ocdid: str) -> str:
    ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    return llm["prompt"].municipality_officials_prompt(known_roles, state=ocdid_parts.state, county=ocdid_parts.county)


def _split_content_into_chunks(content: str, max_chars: int) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    return MarkdownSplitter(max_chars, overlap=_CHUNK_OVERLAP_CHARS).chunks(content)


async def _process_chunks(
    llm: dict,
    source_url: str,
    request_id,
    jurisdiction_ocdid: str,
    content: str,
    prompt: str,
    seed: Optional[int],
    logger,
) -> Tuple[Dict[str, List[LLMPerson]], List[LLMPerson]]:
    chunks = _split_content_into_chunks(content, llm["max_content_chars"](prompt))
    if len(chunks) > 1:
        logger.info(f"Content split into {len(chunks)} chunks for LLM: {llm['name']}")
    all_responses: Dict[str, List[LLMPerson]] = {}
    all_found: List[LLMPerson] = []
    for chunk in chunks:
        responses, found = await process_with_llm(
            source_url, request_id, jurisdiction_ocdid, chunk, prompt, llm, seed=seed,
        )
        for name, people in responses.items():
            all_responses.setdefault(name, []).extend(people)
        all_found.extend(found)
    return all_responses, all_found


def _collect_all_roles(people_by_name: Dict) -> set[str]:
    return {r.strip().lower() for p_list in people_by_name.values() for p in p_list for r in p.roles}


async def process_page_content(
    context: PeopleCollectorContext,
    page_to_process: Link,
) -> Tuple[LinkFrontier, ProcessPageContentStep]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(f"Step 5: {PipelineStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process.url}")

    assert context.data.research_municipality_step is not None, \
        "should never happen — research_municipality_step is required before process_page_content"

    research = context.data.research_municipality_step
    known_roles = research.known_roles
    role_names = config_utils.get_role_names(context.data.role_config)
    setup_data = ProcessingSetup(
        roles=role_names,
        target_role="Mayor",
        target_designations=research.target_designations,
        known_roles=known_roles,
    )
    current_step = get_or_create_step(context)
    identities = research.identities
    content = read_preprocessed_content(context.data.jurisdiction_ocdid, page_to_process)

    frontier, is_relevant = await check_page_relevance(context, page_to_process, content, known_roles)
    if not is_relevant:
        return frontier, current_step

    updated_raw_records, updated_records, heuristics_passed = await run_llm_loop(
        context, page_to_process, content, known_roles, current_step, identities, logger
    )

    updated_progress = calculate_progress(current_step.progress, updated_records, setup_data)

    if heuristics_passed:
        frontier = update_links(context.data.config.url, frontier, page_to_process, logger, role_names, updated_records)
    else:
        frontier = frontier.mark_status(page_to_process.url, LinkStatus.PROCESSED_HEURISTICS_FAIL)

    return frontier, ProcessPageContentStep(
        progress=updated_progress,
        raw_records_by_llm=updated_raw_records,
        records_by_llm=updated_records,
    )


def get_or_create_step(context: PeopleCollectorContext) -> ProcessPageContentStep:
    assert context.data.research_municipality_step is not None, \
        "should never happen — research_municipality_step is required before get_or_create_step"
    expected_count = context.data.research_municipality_step.expected_count
    return context.data.process_page_content_step or create_process_page_content_step(
        required_data=max(MINIMUM_NUM_PEOPLE, expected_count)
    )


def create_process_page_content_step(required_data: int) -> ProcessPageContentStep:
    return ProcessPageContentStep(
        records_by_llm={"open_router": {}},
        raw_records_by_llm={"open_router": {}},
        progress=ProgressState(
            required_data=required_data,
            current_data=0,
            has_target_role=False,
            has_target_designations=False,
        ),
    )


def _resolve_candidate_urls(
    response: RelevantPageResponseSchema,
    content: str,
    known_roles: list[str],
    config_name: Optional[str],
    designations: list[str],
    logger,
) -> Tuple[list[str], Optional[dict]]:
    if response.relevant_urls:
        return response.relevant_urls, None
    combined_designations = designations + known_roles  # token-exact matching
    roles = known_roles + jurisdiction_name_suffix(config_name)  # substring matching
    heuristic_urls = find_heuristic_urls(content, combined_designations, roles=roles)
    if heuristic_urls:
        logger.info(f"LLM returned 0 relevant URLs — falling back to {len(heuristic_urls)} heuristic URL(s)")
        return list(heuristic_urls.keys()), heuristic_urls
    return [], None


async def check_page_relevance(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    known_roles: list[str],
) -> Tuple[LinkFrontier, bool]:
    prompt = open_router_prompt.relevant_page_prompt(page_to_process.url, context.data.config.name or "", known_roles)
    raw_response = await open_router_llm.run_prompt(
        context.request_id,
        context.data.jurisdiction_ocdid,
        prompt,
        response_schema=RelevantPageResponseSchema,
        content=content,
    )
    response = RelevantPageResponseSchema.model_validate(raw_response)

    frontier = context.data.frontier
    existing_records = context.data.process_page_content_step.records_by_llm if context.data.process_page_content_step else {}
    names, designations = extract_names_and_designations(existing_records)
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)

    candidate_urls, url_comments = _resolve_candidate_urls(
        response, content, known_roles, context.data.config.name, designations, logger
    )
    if candidate_urls:
        frontier = add_relevant_urls(
            candidate_urls, frontier, page_to_process.url,
            names, designations + known_roles, logger, url_comments=url_comments,
        )

    if not response.is_relevant:
        frontier = frontier.mark_status(page_to_process.url, LinkStatus.PROCESSED_IRRELEVANT)

    return frontier, response.is_relevant


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

    for llm_idx, llm in enumerate(LLMS):
        if llm.get("with_batch_api", False):
            continue

        prompt = _build_prompt(llm, known_roles, context.data.jurisdiction_ocdid)

        for attempt in range(2):
            seed = attempt or None
            logger.info(f"Running LLM: {llm['name']} seed={seed}")
            llm_responses, all_records_found = await _process_chunks(
                llm, page_to_process.url, context.request_id,
                context.data.jurisdiction_ocdid, content, prompt, seed, logger,
            )
            updated_raw_records, updated_records = update_step_data(
                context.data.jurisdiction_ocdid, llm_responses, identities,
                updated_records, updated_raw_records, context.data.role_config,
            )
            if check_page_heuristics(logger, page_to_process.url, content, all_records_found):
                logger.info(f"Heuristics passed for LLM: {llm['name']}")
                for prev_llm in LLMS[:llm_idx]:
                    if not prev_llm.get("with_batch_api", False):
                        updated_raw_records = wipe_records_by_source_url(updated_raw_records, prev_llm["name"], page_to_process.url)
                        updated_records = wipe_records_by_source_url(updated_records, prev_llm["name"], page_to_process.url)
                return updated_raw_records, updated_records, True

            if attempt == 0:
                logger.info(f"Heuristics failed for LLM: {llm['name']}, retrying.")

        logger.info(f"Heuristics failed after retry for LLM: {llm['name']}, advancing.")
        updated_raw_records = wipe_records_by_source_url(updated_raw_records, llm["name"], page_to_process.url)
        updated_records = wipe_records_by_source_url(updated_records, llm["name"], page_to_process.url)

    logger.warning(f"All LLMs failed heuristics for page: {page_to_process.url}")
    return updated_raw_records, updated_records, False


async def process_with_llm(
    source_url: str,
    request_id,
    jurisdiction_ocdid: str,
    content: str,
    prompt: str,
    llm: dict,
    seed: Optional[int] = None,
) -> Tuple[Dict[str, List[LLMPerson]], List[LLMPerson]]:
    if llm.get("with_batch_api", False):
        raise NotImplementedError(f"Batch API not yet implemented for LLM: {llm['name']}")

    response = await llm["service"].run_prompt(
        request_id, jurisdiction_ocdid, prompt,
        response_schema=PeopleArrayLLMResponseSchema,
        content=content,
        seed=seed,
    )

    processed_people = []
    for p in cast(PeopleArrayLLMResponseSchema, response).people:
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
    updated_raw = copy.deepcopy(existing_raw_records_by_llm)
    for llm_name, llm_people_list in llm_responses.items():
        people_by_name = updated_raw.get(llm_name, {})
        updated_raw[llm_name] = merge_utils.group_people_by_name(merged_identities, people_by_name, llm_people_list)

    logger = log_utils.get_pipeline_run_logger(jurisdiction_ocdid)
    updated_normalized = copy.deepcopy(existing_records_by_llm)
    for llm, people_by_name in updated_raw.items():
        updated_normalized[llm] = {
            name: [normalize_record(logger, person, role_config) for person in people]
            for name, people in people_by_name.items()
        }

    return updated_raw, updated_normalized


def wipe_records_by_source_url(records_by_llm: RecordsByLLM, llm_name: str, source_url: str) -> RecordsByLLM:
    updated = copy.deepcopy(records_by_llm)
    people_by_name = updated.get(llm_name, {})
    updated[llm_name] = {
        name: [p for p in people if p.source_url != source_url]
        for name, people in people_by_name.items()
        if any(p.source_url != source_url for p in people)
    }
    return updated


def normalize_record(logger, record: LLMPerson, role_config=None) -> LLMPerson:
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
        source_url=record.source_url,
    )


def calculate_progress(
    progress: ProgressState,
    records_by_llm: RecordsByLLM,
    setup_data: ProcessingSetup,
) -> ProgressState:
    max_people_count = 0
    has_target_role = False
    has_target_designations = False
    num_target_designations = len(setup_data.target_designations)

    for llm, people_by_name in records_by_llm.items():
        valid_people = [p for p in people_by_name.values() if has_role_and_contact_info(setup_data.roles, p)]
        max_people_count = max(max_people_count, len(valid_people))

        if setup_data.target_role and setup_data.target_role.strip().lower() in _collect_all_roles(people_by_name):
            has_target_role = True

        if num_target_designations == 0:
            has_target_designations = True
        else:
            people_with_designations = [
                p_list for p_list in valid_people
                if any(p.designations and any(d.strip() for d in p.designations) for p in p_list)
            ]
            if len(people_with_designations) >= num_target_designations:
                has_target_designations = True

    known_roles_lower = {r.strip().lower() for r in setup_data.known_roles}
    requires_mayor = not known_roles_lower or "mayor" in known_roles_lower

    return ProgressState(
        required_data=progress.required_data,
        current_data=max_people_count,
        has_target_role=has_target_role if requires_mayor else True,
        has_target_designations=has_target_designations,
    )


def read_preprocessed_content(jurisdiction_ocdid: str, page_to_process: Link) -> str:
    cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
    content_file_path = os.path.join(cache_path, page_to_process.folder_name, "preprocessed.md")
    with open(content_file_path, "r", encoding="utf-8") as f:
        return f.read()
