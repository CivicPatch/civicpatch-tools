"""One handler per state of GOVERNING_LAW_COLLECTOR_TRANSITIONS. Each takes the context and
answers it with the next state; the engine checks the answer against the graph."""

from datetime import datetime, timezone

import httpx
import services.civicpatch_api as civicpatch_api
from runners.governing_law_collector import converters, fetchers, finders
from runners.governing_law_collector.schemas import GoverningLawCollectorContext, GoverningLawCollectorState, GoverningLawCollectorStep
from shared.schemas import GoverningLaw, GoverningLawKind, JurisdictionExtras, PipelineRunLimits
from shared.utils.statuses import PipelineRunStatus
from utils import cost_utils
from utils.log_utils import PipelineRunLogger

Step = tuple[GoverningLawCollectorContext, GoverningLawCollectorState]


def _next(context: GoverningLawCollectorContext, **data_updates) -> GoverningLawCollectorContext:
    return context.model_copy(update={"data": context.data.model_copy(update=data_updates)})


def _after_url(context: GoverningLawCollectorContext, **data_updates) -> Step:
    """Done with the url in hand: the next one, or write what was stored."""
    remaining = context.data.pending_urls[1:]
    next_context = _next(context, pending_urls=remaining, fetched=None, markdown=None, escalate=False, **data_updates)
    return next_context, GoverningLawCollectorStep.FETCH_SOURCE if remaining else GoverningLawCollectorStep.WRITE_GOVERNING_LAW


async def start(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, GoverningLawCollectorStep.FIND_SOURCE


async def find_source(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    answer = await finders.find(context.data.config)
    logger.info(f"{answer.found_by}: {len(answer.charter_urls)} charter url(s), {len(answer.general_law_urls)} general law url(s)")
    next_context = _next(context, answer=answer, pending_urls=answer.urls)
    return next_context, GoverningLawCollectorStep.FETCH_SOURCE if answer.urls else GoverningLawCollectorStep.WRITE_GOVERNING_LAW


async def fetch_source(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: GoverningLawCollectorContext, client: httpx.AsyncClient) -> Step:
    url = context.data.pending_urls[0]
    if not context.data.escalate:
        reused = await civicpatch_api.reuse_governing_law_source_page(client, context.data.jurisdiction_ocdid, url)
        if reused is not None:
            logger.info(f"{url}: stored by another run within a day, not fetched again")
            return _recorded(context, url, reused["id"])
    try:
        page = await fetchers.fetch(url, by_browser=context.data.escalate)
    except fetchers.RefusedByHost as refused:
        logger.warning(f"{url}: refused with {refused.status_code}, not retried")
        return _after_url(context, skipped_urls=[*context.data.skipped_urls, url])
    return _next(context, fetched=page), GoverningLawCollectorStep.PREPROCESS_PAGE_CONTENT


async def preprocess_page_content(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    page = context.data.fetched
    assert page is not None, "FETCH_SOURCE always leaves a page for PREPROCESS_PAGE_CONTENT"
    markdown = converters.to_markdown(page)
    if not converters.is_thin(markdown):
        return _next(context, fetched=None, markdown=markdown), GoverningLawCollectorStep.STORE_SOURCE_PAGE
    if not page.by_browser:
        logger.info(f"{page.url}: thin by plain GET, fetching again by browser")
        return _next(context, fetched=None, escalate=True), GoverningLawCollectorStep.FETCH_SOURCE
    logger.warning(f"{page.url}: thin even by browser, skipped")
    return _after_url(context, skipped_urls=[*context.data.skipped_urls, context.data.pending_urls[0]])


async def store_source_page(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, client: httpx.AsyncClient) -> Step:
    markdown = context.data.markdown
    assert markdown is not None, "PREPROCESS_PAGE_CONTENT always leaves markdown for STORE_SOURCE_PAGE"
    url = context.data.pending_urls[0]
    stored = await civicpatch_api.store_governing_law_source_page(client, context.data.jurisdiction_ocdid, url, markdown)
    return _recorded(context, url, stored["id"])


def _recorded(context: GoverningLawCollectorContext, url: str, source_page_id: str) -> Step:
    if _is_charter(context, url):
        return _after_url(context, charter_source_page_ids=[*context.data.charter_source_page_ids, source_page_id])
    return _after_url(context, general_law_source_page_ids=[*context.data.general_law_source_page_ids, source_page_id])


async def write_governing_law(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, client: httpx.AsyncClient) -> Step:
    governing_law = governing_law_from(context)
    await civicpatch_api.patch_jurisdiction_extras(
        client, context.data.jurisdiction_ocdid, JurisdictionExtras(extras_governing_law=governing_law)
    )
    return _next(context, governing_law=governing_law), PipelineRunStatus.SUCCESS


async def send_error(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, PipelineRunStatus.ERROR


def _is_charter(context: GoverningLawCollectorContext, url: str) -> bool:
    answer = context.data.answer
    return answer is not None and url in answer.charter_urls


def governing_law_from(context: GoverningLawCollectorContext) -> GoverningLaw:
    """What the run stored decides the kind, not what the finder hoped for: a charter if one was
    stored, else general law if a statute was, else none found."""
    answer = context.data.answer
    assert answer is not None, "FIND_SOURCE always answers before WRITE_GOVERNING_LAW"
    charter, general_law = context.data.charter_source_page_ids, context.data.general_law_source_page_ids
    kind = GoverningLawKind.CHARTER if charter else GoverningLawKind.GENERAL_LAW if general_law else GoverningLawKind.NONE_FOUND
    return GoverningLaw(
        kind=kind,
        classification=answer.classification,
        found_by=answer.found_by,
        source_page_ids=[*charter, *general_law],
        collected_at=datetime.now(timezone.utc),
        cost_usd=cost_utils.total_cost(context.pipeline_run_id),
    )


TRANSITION_MAP = {
    PipelineRunStatus.INIT: start,
    GoverningLawCollectorStep.FIND_SOURCE: find_source,
    GoverningLawCollectorStep.FETCH_SOURCE: fetch_source,
    GoverningLawCollectorStep.PREPROCESS_PAGE_CONTENT: preprocess_page_content,
    GoverningLawCollectorStep.STORE_SOURCE_PAGE: store_source_page,
    GoverningLawCollectorStep.WRITE_GOVERNING_LAW: write_governing_law,
    PipelineRunStatus.SEND_ERROR: send_error,
}
