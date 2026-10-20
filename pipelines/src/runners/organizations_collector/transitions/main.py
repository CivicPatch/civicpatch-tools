"""One handler per state of ORGANIZATIONS_COLLECTOR_TRANSITIONS. Each takes the context and
answers it with the next state; the engine checks the answer against the graph. Plan 2's 2.11
to 2.15 fill in SELECT_SECTIONS, EXTRACT, VERIFY and WRITE."""

from typing import List

import httpx
import services.civicpatch_api as civicpatch_api
import services.open_router.llm as open_router_llm
import services.open_router.prompts as open_router_prompts
from runners.organizations_collector import sections
from runners.organizations_collector.schemas import (
    GoverningSectionsResponse,
    OrganizationsCollectorContext,
    OrganizationsCollectorState,
    OrganizationsCollectorStep,
)
from shared.schemas import PipelineRunLimits
from shared.utils.statuses import PipelineRunStatus
from utils.log_utils import PipelineRunLogger

Step = tuple[OrganizationsCollectorContext, OrganizationsCollectorState]


async def start(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, OrganizationsCollectorStep.SELECT_SECTIONS


async def select_sections(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: OrganizationsCollectorContext, client: httpx.AsyncClient) -> Step:
    governing_law = context.data.config.governing_law
    if governing_law is None or not governing_law.source_page_ids:
        logger.info("no cached law to read")
        return context, OrganizationsCollectorStep.WRITE
    pages = [
        sections.GoverningLawPage.model_validate(
            await civicpatch_api.get_governing_law_source_page(client, context.data.jurisdiction_ocdid, page_id)
        )
        for page_id in governing_law.source_page_ids
    ]
    selected_governing_law_text = await _selected_governing_law_text(context, logger, pages)
    return _next(context, selected_governing_law_text=selected_governing_law_text), OrganizationsCollectorStep.EXTRACT


async def _selected_governing_law_text(context: OrganizationsCollectorContext, logger: PipelineRunLogger, pages: List[sections.GoverningLawPage]) -> str:
    """All of it when it fits; else the sections picked from their headings, else those whose
    headings name the government; a text with no sections to pick from goes whole."""
    whole = "\n\n".join(page.text for page in pages)
    found = sections.split_sections(pages)
    if sections.fits_whole(whole) or not found:
        return whole
    chosen = sections.picked(found, await _pick(context, found)) or sections.keyword_sections(found)
    logger.info(f"{len(whole):,} chars in {len(found)} sections: reading {len(chosen)}")
    return sections.joined(chosen) if chosen else whole


async def _pick(context: OrganizationsCollectorContext, found: List[sections.Section]) -> List[str]:
    response = await open_router_llm.run_prompt(
        context.pipeline_run_id,
        context.data.jurisdiction_ocdid,
        open_router_prompts.governing_sections_prompt(),
        prompt_name="governing_sections",
        response_schema=GoverningSectionsResponse,
        content=sections.heading_listing(found),
    )
    return GoverningSectionsResponse.model_validate(response).sections


def _next(context: OrganizationsCollectorContext, **data_updates) -> OrganizationsCollectorContext:
    return context.model_copy(update={"data": context.data.model_copy(update=data_updates)})


async def extract(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, OrganizationsCollectorStep.VERIFY


async def verify(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, OrganizationsCollectorStep.WRITE


async def write(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, PipelineRunStatus.SUCCESS


async def send_error(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: OrganizationsCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, PipelineRunStatus.ERROR


TRANSITION_MAP = {
    PipelineRunStatus.INIT: start,
    OrganizationsCollectorStep.SELECT_SECTIONS: select_sections,
    OrganizationsCollectorStep.EXTRACT: extract,
    OrganizationsCollectorStep.VERIFY: verify,
    OrganizationsCollectorStep.WRITE: write,
    PipelineRunStatus.SEND_ERROR: send_error,
}
