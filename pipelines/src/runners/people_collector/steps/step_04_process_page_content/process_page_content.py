import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, cast

import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompt
import shared.utils.name_utils as name_utils
from runners.people_collector.schemas import (
    Link,
    LinkFrontier,
    LinkStatus,
    LLMPersonRecord,
    PeopleArrayLLMResponseSchema,
    PeopleByName,
    PeopleCollectorContext,
    PipelineStatus,
    ProcessPageContentStep,
    ProgressState,
    RelevantPageResponseSchema,
)
from runners.people_collector.steps.step_04_process_page_content.heuristics import (
    check_page_heuristics,
)
from runners.people_collector.utils.link_discovery import (
    add_relevant_urls,
    extract_names_and_designations,
    find_heuristic_urls,
    has_role_and_contact_info,
    jurisdiction_name_suffix,
    update_links,
)
from semantic_text_splitter import MarkdownSplitter
from shared.utils import (
    config_utils,
    data_path_utils,
    id_utils,
    url_utils,
)
from utils import log_utils, merge_utils


@dataclass
class ProcessingSetup:
    roles: List[str]
    target_role: str
    target_designations: List[str]
    known_roles: List[str]


MINIMUM_NUM_PEOPLE = 5
_CHUNK_OVERLAP_CHARS = 500


def _build_prompt(known_roles: list[str], jurisdiction_ocdid: str) -> str:
    ocdid_parts = id_utils.parse_jurisdiction_ocdid(jurisdiction_ocdid)
    return open_router_prompt.municipality_officials_prompt(
        known_roles, state=ocdid_parts.state, county=ocdid_parts.county
    )


def _split_content_into_chunks(content: str, max_chars: int) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    return MarkdownSplitter(max_chars, overlap=_CHUNK_OVERLAP_CHARS).chunks(content)


async def _process_with_llm_in_chunks(
    source_url: str,
    request_id,
    jurisdiction_ocdid: str,
    content: str,
    prompt: str,
    seed: Optional[int],
    logger,
) -> List[LLMPersonRecord]:
    chunks = _split_content_into_chunks(
        content, open_router_llm.max_content_chars(prompt)
    )
    if len(chunks) > 1:
        logger.info(f"Content split into {len(chunks)} chunks for LLM: open_router")
    all_found: List[LLMPersonRecord] = []
    for chunk in chunks:
        found = await process_with_llm(
            source_url,
            request_id,
            jurisdiction_ocdid,
            chunk,
            prompt,
            seed=seed,
        )
        all_found.extend(found)
    return all_found


def _collect_all_roles(
    role_config: config_utils.RoleConfig, people_by_name: Dict
) -> set[str]:
    # TBD: normalize and keep only role configs
    return {
        r.strip().lower()
        for p_list in people_by_name.values()
        for p in p_list
        for r in p.roles
    }


async def process_page_content(
    context: PeopleCollectorContext,
    page_to_process: Link,
) -> Tuple[LinkFrontier, ProcessPageContentStep]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(
        f"Step 5: {PipelineStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process.url}"
    )

    assert context.data.research_municipality_step is not None, (
        "should never happen — research_municipality_step is required before process_page_content"
    )

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
    content = read_preprocessed_content(
        context.data.jurisdiction_ocdid, page_to_process
    )

    frontier, is_relevant = await check_page_relevance(
        context, page_to_process, content, known_roles
    )
    if not is_relevant:
        return frontier, current_step

    updated_records, heuristics_passed = await collect_page_records(
        context, page_to_process, content, known_roles, current_step, identities, logger
    )

    updated_progress = calculate_progress(
        context.data.role_config, current_step.progress, updated_records, setup_data
    )

    if heuristics_passed:
        frontier = update_links(
            context.data.config.url,
            frontier,
            page_to_process,
            logger,
            role_names,
            updated_records,
        )
    else:
        frontier = frontier.mark_status(
            page_to_process.url, LinkStatus.PROCESSED_HEURISTICS_FAIL
        )

    return frontier, ProcessPageContentStep(
        progress=updated_progress,
        records=updated_records,
    )


def get_or_create_step(context: PeopleCollectorContext) -> ProcessPageContentStep:
    assert context.data.research_municipality_step is not None, (
        "should never happen — research_municipality_step is required before get_or_create_step"
    )
    expected_count = context.data.research_municipality_step.expected_count
    return context.data.process_page_content_step or create_process_page_content_step(
        required_data=max(MINIMUM_NUM_PEOPLE, expected_count)
    )


def create_process_page_content_step(required_data: int) -> ProcessPageContentStep:
    return ProcessPageContentStep(
        records={},
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
        logger.info(
            f"LLM returned 0 relevant URLs — falling back to {len(heuristic_urls)} heuristic URL(s)"
        )
        return list(heuristic_urls.keys()), heuristic_urls
    return [], None


async def check_page_relevance(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    known_roles: list[str],
) -> Tuple[LinkFrontier, bool]:
    prompt = open_router_prompt.relevant_page_prompt(
        page_to_process.url, context.data.config.name or "", known_roles
    )
    raw_response = await open_router_llm.run_prompt(
        context.request_id,
        context.data.jurisdiction_ocdid,
        prompt,
        response_schema=RelevantPageResponseSchema,
        content=content,
    )
    response = RelevantPageResponseSchema.model_validate(raw_response)

    frontier = context.data.frontier
    existing_records = (
        context.data.process_page_content_step.records
        if context.data.process_page_content_step
        else {}
    )
    names, designations = extract_names_and_designations(existing_records)
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)

    candidate_urls, url_comments = _resolve_candidate_urls(
        response, content, known_roles, context.data.config.name, designations, logger
    )
    if candidate_urls:
        frontier = add_relevant_urls(
            candidate_urls,
            frontier,
            page_to_process.url,
            names,
            designations + known_roles,
            logger,
            url_comments=url_comments,
        )

    if not response.is_relevant:
        frontier = frontier.mark_status(
            page_to_process.url, LinkStatus.PROCESSED_IRRELEVANT
        )

    return frontier, response.is_relevant


async def collect_page_records(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    known_roles: list[str],
    current_step: ProcessPageContentStep,
    identities: Dict,
    logger,
) -> Tuple[PeopleByName, bool]:
    prompt = _build_prompt(known_roles, context.data.jurisdiction_ocdid)

    for attempt in range(2):
        seed = attempt or None
        logger.info(f"Running LLM: openrouter_seed seed={seed}")
        people_found_in_page = await _process_with_llm_in_chunks(
            page_to_process.url,
            context.request_id,
            context.data.jurisdiction_ocdid,
            content,
            prompt,
            seed,
            logger,
        )

        updated_records = merge_utils.group_people_by_name(
            identities, current_step.records, people_found_in_page
        )

        if check_page_heuristics(
            logger, page_to_process.url, content, people_found_in_page
        ):
            logger.info(f"Heuristics passed for LLM: {page_to_process.url}")
            return updated_records, True

        if attempt == 0:
            logger.info(
                f"Heuristics failed for LLM: open_router, retrying: {page_to_process.url}"
            )

    logger.warning(
        f"Failed heuristics for page after all attempts, skipping page: {page_to_process.url}"
    )
    return current_step.records, False


async def process_with_llm(
    source_url: str,
    request_id,
    jurisdiction_ocdid: str,
    content: str,
    prompt: str,
    seed: Optional[int] = None,
) -> List[LLMPersonRecord]:
    response = await open_router_llm.run_prompt(
        request_id,
        jurisdiction_ocdid,
        prompt,
        response_schema=PeopleArrayLLMResponseSchema,
        content=content,
        seed=seed,
    )

    processed_people = []
    for p in cast(PeopleArrayLLMResponseSchema, response).people:
        p = p.model_dump()
        p["name"] = name_utils.reorder_name_if_inverted(p["name"])
        if not p.get("name") or not p["name"].strip():
            continue
        p["source_url"] = source_url
        if p["url"]:
            p["url"] = url_utils.format_url(p["url"])
        processed_people.append(LLMPersonRecord.model_validate(p))

    return processed_people


def calculate_progress(
    role_config: config_utils.RoleConfig,
    progress: ProgressState,
    records: PeopleByName,
    setup_data: ProcessingSetup,
) -> ProgressState:
    has_target_role = False
    has_target_designations = False
    num_target_designations = len(setup_data.target_designations)

    valid_people = [
        p for p in records.values() if has_role_and_contact_info(setup_data.roles, p)
    ]
    max_people_count = len(valid_people)

    if (
        setup_data.target_role
        and setup_data.target_role.strip().lower()
        in _collect_all_roles(role_config, records)
    ):
        has_target_role = True

    if num_target_designations == 0:
        has_target_designations = True
    else:
        people_with_designations = [
            p_list
            for p_list in valid_people
            if any(
                p.designations and any(d.strip() for d in p.designations)
                for p in p_list
            )
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
    content_file_path = os.path.join(
        cache_path, page_to_process.folder_name, "preprocessed.md"
    )
    with open(content_file_path, "r", encoding="utf-8") as f:
        return f.read()
