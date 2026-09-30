import asyncio
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, cast

import services.open_router.llm as open_router_llm
import shared.utils.name_utils as name_utils
from runners.people_collector.schemas import (
    ExpectedMembership,
    Link,
    LinkFrontier,
    LinkStatus,
    OrganizationCoverageResponseSchema,
    PersonSourceRecord,
    PeopleArrayLLMResponseSchema,
    PeopleByName,
    PeopleCollectorContext,
    PipelineStatus,
    ProcessPageContentStep,
    ProgressState,
    RelevantPageResponseSchema,
)
from runners.people_collector.steps.step_04_process_page_content.organization_progress import (
    organization_needs,
    organizations_progress,
)
from runners.people_collector.steps.step_04_process_page_content.extraction_scopes import (
    ExtractionScope,
    extraction_scopes,
)
from runners.people_collector.steps.step_04_process_page_content.heuristics import (
    check_page_heuristics,
)
from runners.people_collector.steps.step_04_process_page_content.heuristics_failure import (
    HeuristicsFailure,
)
from shared.schemas import LOCAL_IMAGE_PREFIX, KnownOrganization
from runners.people_collector.utils.organization_terms import (
    as_tokens,
    expected_roles,
    roles_to_look_for,
    search_phrases,
)
from runners.people_collector.utils.link_discovery import (
    add_relevant_urls,
    extract_names_and_designations,
    find_heuristic_urls,
    has_role_and_contact_info,
    jurisdiction_name_suffix,
    update_links,
)
from pydantic import BaseModel
from semantic_text_splitter import MarkdownSplitter
from shared.utils import (
    config_utils,
    data_path_utils,
    url_utils,
)
from shared.utils import merge_utils
from utils import log_utils
from runners.people_collector.steps.step_04_process_page_content.page_prompts import (
    coverage_prompt,
    extraction_prompt,
    prompt_hash,
    relevance_prompt,
)
from runners.people_collector.steps.step_04_process_page_content.unchanged_pages import (
    is_unchanged,
    published_source_page,
    source_page_relevance,
)
from shared.schemas import PublishedSourcePage
from shared.utils.content_hash import content_hash
from shared.utils.label_parser import ParsedLabel, parse_label
from shared.utils.taxonomy import Taxonomy, build_taxonomy, lookup_key


@dataclass
class ProcessingSetup:
    roles: List[str]
    known_organizations: List[KnownOrganization]
    expected_memberships: List[ExpectedMembership]


MINIMUM_NUM_PEOPLE = 5
_CHUNK_OVERLAP_CHARS = 500


def _split_content_into_chunks(content: str, max_chars: int) -> list[str]:
    if len(content) <= max_chars:
        return [content]
    return MarkdownSplitter(max_chars, overlap=_CHUNK_OVERLAP_CHARS).chunks(content)


async def _process_with_llm_in_chunks(
    source_url: str,
    pipeline_run_id,
    jurisdiction_ocdid: str,
    content: str,
    prompt: str,
    seed: Optional[int],
    logger,
) -> List[PersonSourceRecord]:
    chunks = _split_content_into_chunks(
        content, open_router_llm.max_content_chars(prompt)
    )
    if len(chunks) > 1:
        logger.info(f"Content split into {len(chunks)} chunks for LLM: open_router")
    all_found: List[PersonSourceRecord] = []
    # 1-based: a row saying "chunk 1 of 3" reads without the reader doing arithmetic.
    for index, chunk in enumerate(chunks, start=1):
        found = await process_with_llm(
            source_url,
            pipeline_run_id,
            jurisdiction_ocdid,
            chunk,
            prompt,
            seed=seed,
            chunk_index=index,
            chunk_count=len(chunks),
        )
        all_found.extend(found)
    return all_found


# Expected divisions come from the division_ocdids on the roster we already hold, so they have
# the same staleness as required_data: a ward that was renamed, merged or dropped leaves a
# target no scrape can reach. Floored at one so it stays a real signal — a jurisdiction with
# divisions must still place somebody in one, it just need not place everybody.
DIVISION_REQUIREMENT_TOLERANCE = 2


def required_division_count(num_target_divisions: int) -> int:
    if num_target_divisions == 0:
        return 0
    return max(1, num_target_divisions - DIVISION_REQUIREMENT_TOLERANCE)


def _names_a_division(parsed: ParsedLabel) -> bool:
    """Whether the label places the person in a division — a ward, district or seat number.

    Divisions only: `ExpectedMembership.division` is built by `divisions.filter_divisions`, so counting
    `other_designations` here compared a person against a target they were never measured on,
    and a jurisdiction with no districts could satisfy the target on a seat marker alone.
    """
    return bool(parsed.division)


def _resolved_roles(taxonomy: Taxonomy, records: PeopleByName) -> set[str]:
    found = set()
    for group in records.values():
        for record in group:
            canonical = parse_label(record.label, taxonomy).role
            if canonical:
                found.add(lookup_key(canonical))
    return found


def found_every_expected_role(
    taxonomy: Taxonomy, records: PeopleByName, expected: List[ExpectedMembership]
) -> bool:
    """Any record naming the role counts, contact details or not: this asks whether the office
    was seen at all, which is how a missing mayor keeps an otherwise complete council crawling."""
    found = _resolved_roles(taxonomy, records)
    return all(lookup_key(role) in found for role in expected_roles(expected))


async def process_page_content(
    context: PeopleCollectorContext,
    page_to_process: Link,
) -> Tuple[LinkFrontier, ProcessPageContentStep]:
    logger = log_utils.get_pipeline_run_logger(context.data.jurisdiction_ocdid)
    logger.info(
        f"Step 4: {PipelineStatus.PROCESS_PAGE_CONTENT.value}: {page_to_process.url}"
    )

    assert context.data.research_municipality_step is not None, (
        "should never happen — research_municipality_step is required before process_page_content"
    )

    research = context.data.research_municipality_step
    taxonomy = build_taxonomy(context.data.role_config)
    known_roles = roles_to_look_for(research.expected_memberships, research.known_organizations)
    role_names = config_utils.get_role_names(context.data.role_config)
    setup_data = ProcessingSetup(
        roles=role_names,
        known_organizations=research.known_organizations,
        expected_memberships=research.expected_memberships,
    )
    current_step = get_or_create_step(context)
    identities = research.identities
    content = read_preprocessed_content(
        context.data.jurisdiction_ocdid, page_to_process
    )

    page_hash = content_hash(content)
    page_prompt_hash = prompt_hash(
        page_to_process.url,
        context.data.config,
        context.data.jurisdiction_ocdid,
        known_roles,
        research.known_organizations,
    )
    published = published_source_page(
        context.data.config.published_source_pages, page_to_process.url
    )
    if published is not None and not is_unchanged(published, page_hash, page_prompt_hash):
        published = None
    if published:
        logger.info(
            f"Unchanged since {published.read_source_page_id}, using the published reading: "
            f"{page_to_process.url}"
        )
        frontier, is_relevant = apply_relevance(
            context,
            page_to_process,
            content,
            source_page_relevance(published),
            known_roles,
            research.known_organizations,
            research.expected_memberships,
        )
    else:
        frontier, is_relevant = await check_page_relevance(
            context,
            page_to_process,
            content,
            known_roles,
            research.known_organizations,
            research.expected_memberships,
        )
    frontier = frontier.update_link(
        page_to_process.url,
        page_hash=page_hash,
        prompt_hash=page_prompt_hash,
        unchanged_since_source_page_id=published.read_source_page_id if published else None,
    )
    if not is_relevant:
        return frontier, current_step

    if published:
        extraction = source_page_extraction(published, current_step, identities)
    else:
        extraction = await collect_page_records(
            context,
            page_to_process,
            content,
            known_roles,
            research.known_organizations,
            current_step,
            identities,
            logger,
        )
    updated_records = extraction.records

    updated_progress = calculate_progress(
        taxonomy, current_step.progress, updated_records, setup_data
    )

    if extraction.heuristics_passed:
        frontier = update_links(
            context.data.config.url,
            frontier,
            page_to_process,
            logger,
            taxonomy,
            role_names,
            updated_records,
            organization_needs(
                research.known_organizations,
                research.expected_memberships,
                updated_records,
                taxonomy,
            ),
        )
    else:
        frontier = frontier.mark_status(
            page_to_process.url, LinkStatus.PROCESSED_HEURISTICS_FAIL
        )
    frontier = frontier.update_link(
        page_to_process.url,
        heuristics_failures=extraction.heuristics_failures,
        organization_ids=extraction.organization_ids,
    )

    return frontier, ProcessPageContentStep(
        progress=updated_progress,
        records=updated_records,
    )


def get_or_create_step(context: PeopleCollectorContext) -> ProcessPageContentStep:
    assert context.data.research_municipality_step is not None, (
        "should never happen — research_municipality_step is required before get_or_create_step"
    )
    expected = context.data.research_municipality_step.expected_memberships
    return context.data.process_page_content_step or create_process_page_content_step(
        required_data=max(MINIMUM_NUM_PEOPLE, len(expected))
    )


def create_process_page_content_step(required_data: int) -> ProcessPageContentStep:
    return ProcessPageContentStep(
        records={},
        progress=ProgressState(
            required_data=required_data,
            current_data=0,
            has_target_roles=False,
            has_target_divisions=False,
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
    known_organizations: List[KnownOrganization],
    expected_memberships: List[ExpectedMembership],
) -> Tuple[LinkFrontier, bool]:
    prompt = relevance_prompt(
        page_to_process.url, context.data.config, known_roles, known_organizations
    )
    raw_response = await open_router_llm.run_prompt(
        context.pipeline_run_id,
        context.data.jurisdiction_ocdid,
        prompt,
        prompt_name="relevant_page",
        response_schema=RelevantPageResponseSchema,
        content=content,
        source_url=page_to_process.url,
    )
    response = RelevantPageResponseSchema.model_validate(raw_response)
    return apply_relevance(
        context,
        page_to_process,
        content,
        response,
        known_roles,
        known_organizations,
        expected_memberships,
    )


def apply_relevance(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    response: RelevantPageResponseSchema,
    known_roles: list[str],
    known_organizations: List[KnownOrganization],
    expected_memberships: List[ExpectedMembership],
) -> Tuple[LinkFrontier, bool]:
    """Record a relevance answer and queue the links it proposed, whether the LLM just gave it
    or it came from an unchanged page's published row."""
    frontier = context.data.frontier.update_link(
        page_to_process.url,
        is_relevant=response.is_relevant,
        relevant_urls=response.relevant_urls,
    )
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
            organization_needs(
                known_organizations,
                expected_memberships,
                existing_records,
                build_taxonomy(context.data.role_config),
            ),
            names,
            # Organizations and their posts as well as roles: the queue ranks a designation match
            # above reference count, and an organization whose wording no role covers had nothing to
            # match on at all.
            designations
            + as_tokens(search_phrases(known_organizations, expected_memberships)),
            logger,
            url_comments=url_comments,
        )

    if not response.is_relevant:
        frontier = frontier.mark_status(
            page_to_process.url, LinkStatus.PROCESSED_IRRELEVANT
        )

    return frontier, response.is_relevant


async def organizations_covered(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    organizations: List[KnownOrganization],
) -> List[str]:
    """Which organizations this page carries people for, one narrow question each.

    Only worth asking where there are organizations to tell apart, and only on a page already judged
    relevant, so the calls land on the minority of pages that are worth extracting from at all.
    """
    if len(organizations) < 2:
        return []
    answers = await asyncio.gather(
        *(
            open_router_llm.run_prompt(
                context.pipeline_run_id,
                context.data.jurisdiction_ocdid,
                coverage_prompt(organization, context.data.config),
                prompt_name="page_covers_organization",
                response_schema=OrganizationCoverageResponseSchema,
                content=content,
                source_url=page_to_process.url,
            )
            for organization in organizations
        )
    )
    return [
        organization.name
        for organization, answer in zip(organizations, answers)
        if OrganizationCoverageResponseSchema.model_validate(answer).covers
    ]


def covered_organization_ids(
    organizations: List[KnownOrganization], covers: List[str]
) -> List[str]:
    """The page's own answer, for a page already judged relevant. A single organization is never
    asked, so relevant means it; an empty answer stays empty even though extraction then runs
    for every organization."""
    if len(organizations) == 1:
        return [organizations[0].id]
    return [organization.id for organization in organizations if organization.name in covers]


class PageExtraction(BaseModel):
    records: PeopleByName
    # True if any organization's extraction passed.
    heuristics_passed: bool
    heuristics_failures: List[HeuristicsFailure]
    organization_ids: List[str]


def source_page_extraction(
    source_page: PublishedSourcePage, current_step: ProcessPageContentStep, identities: Dict
) -> PageExtraction:
    """The records the page gave last time, merged exactly as fresh ones would be. A replay is
    a full reading: without it the page's people would look absent and retire."""
    return PageExtraction(
        records=merge_utils.group_people_by_name(
            identities, current_step.records, list(source_page.known_records)
        ),
        heuristics_passed=True,
        heuristics_failures=[],
        organization_ids=source_page.organization_ids,
    )


async def collect_page_records(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    known_roles: list[str],
    organizations: List[KnownOrganization],
    current_step: ProcessPageContentStep,
    identities: Dict,
    logger,
) -> PageExtraction:
    """One extraction per organization the page covers. An organization whose results fail the
    heuristics twice adds nothing from this page; the others' still count."""
    found: List[PersonSourceRecord] = []
    failures: List[HeuristicsFailure] = []
    any_passed = False
    covers = await organizations_covered(context, page_to_process, content, organizations)
    organization_ids = covered_organization_ids(organizations, covers)
    for scope in extraction_scopes(organizations, covers):
        scoped, scope_failures = await _extract_for_scope(
            context, page_to_process, content, known_roles, scope, logger
        )
        failures.extend(scope_failures)
        if scoped is not None:
            found.extend(scoped)
            any_passed = True

    if not any_passed:
        logger.warning(
            f"Failed heuristics for page after all attempts, skipping page: {page_to_process.url}"
        )
        return PageExtraction(
            records=current_step.records,
            heuristics_passed=False,
            heuristics_failures=failures,
            organization_ids=organization_ids,
        )
    return PageExtraction(
        records=merge_utils.group_people_by_name(identities, current_step.records, found),
        heuristics_passed=True,
        heuristics_failures=failures,
        organization_ids=organization_ids,
    )


async def _extract_for_scope(
    context: PeopleCollectorContext,
    page_to_process: Link,
    content: str,
    known_roles: list[str],
    scope: ExtractionScope,
    logger,
) -> Tuple[Optional[List[PersonSourceRecord]], List[HeuristicsFailure]]:
    """This organization's records, stamped with its id — or None if they failed the heuristics
    twice — and the reason each failed attempt gave."""
    prompt = extraction_prompt(known_roles, context.data.jurisdiction_ocdid, scope)
    organization = scope.prompt_organization.name if scope.prompt_organization else "unscoped"
    failures: List[HeuristicsFailure] = []

    for attempt in range(2):
        seed = attempt or None
        logger.info(f"Running LLM: openrouter_seed seed={seed} organization={organization}")
        people_found_in_page = await _process_with_llm_in_chunks(
            page_to_process.url,
            context.pipeline_run_id,
            context.data.jurisdiction_ocdid,
            content,
            prompt,
            seed,
            logger,
        )
        failure = check_page_heuristics(
            logger, page_to_process.url, content, people_found_in_page
        )
        if failure is None:
            logger.info(f"Heuristics passed for LLM: {page_to_process.url} organization={organization}")
            return [
                record.model_copy(update={"organization_id": scope.organization_id})
                for record in people_found_in_page
            ], failures
        failures.append(failure)
        if attempt == 0:
            logger.info(
                f"Heuristics failed for LLM: open_router, retrying: {page_to_process.url} organization={organization}"
            )
    return None, failures


async def process_with_llm(
    source_url: str,
    pipeline_run_id,
    jurisdiction_ocdid: str,
    content: str,
    prompt: str,
    seed: Optional[int] = None,
    chunk_index: Optional[int] = None,
    chunk_count: Optional[int] = None,
) -> List[PersonSourceRecord]:
    response = await open_router_llm.run_prompt(
        pipeline_run_id,
        jurisdiction_ocdid,
        prompt,
        prompt_name="municipality_officials",
        response_schema=PeopleArrayLLMResponseSchema,
        content=content,
        seed=seed,
        source_url=source_url,
        chunk_index=chunk_index,
        chunk_count=chunk_count,
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
        p["image"] = _downloaded_image(p.get("image"))
        processed_people.append(PersonSourceRecord.model_validate(p))

    return processed_people


def _downloaded_image(image: Optional[str]) -> Optional[str]:
    """Only a photo `scrape_images` downloaded can be served. The extractor copies whatever src
    sits beside a person, and has wrapped a real `local://` hash in a url it made up."""
    return image if image and image.startswith(LOCAL_IMAGE_PREFIX) else None


def calculate_progress(
    taxonomy: Taxonomy,
    progress: ProgressState,
    records: PeopleByName,
    setup_data: ProcessingSetup,
) -> ProgressState:
    has_target_divisions = False
    num_target_divisions = sum(
        1 for membership in setup_data.expected_memberships if membership.division
    )

    valid_people = [
        p for p in records.values() if has_role_and_contact_info(taxonomy, p)
    ]
    max_people_count = len(valid_people)

    if num_target_divisions == 0:
        has_target_divisions = True
    else:
        people_with_divisions = [
            p_list
            for p_list in valid_people
            if any(
                _names_a_division(parse_label(p.label, taxonomy)) for p in p_list
            )
        ]
        if len(people_with_divisions) >= required_division_count(num_target_divisions):
            has_target_divisions = True

    return ProgressState(
        required_data=progress.required_data,
        current_data=max_people_count,
        has_target_roles=found_every_expected_role(
            taxonomy, records, setup_data.expected_memberships
        ),
        has_target_divisions=has_target_divisions,
        organizations=organizations_progress(
            setup_data.known_organizations, setup_data.expected_memberships, records, taxonomy
        ),
    )


def read_preprocessed_content(jurisdiction_ocdid: str, page_to_process: Link) -> str:
    cache_path = data_path_utils.get_cache_path(jurisdiction_ocdid)
    content_file_path = os.path.join(
        cache_path, page_to_process.folder_name, "preprocessed.md"
    )
    with open(content_file_path, "r", encoding="utf-8") as f:
        return f.read()
