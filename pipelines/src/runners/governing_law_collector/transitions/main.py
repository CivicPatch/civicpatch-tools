"""One handler per state of GOVERNING_LAW_COLLECTOR_TRANSITIONS. Each takes the context and
answers it with the next state; the engine checks the answer against the graph."""

from datetime import datetime, timezone

import httpx
import services.civicpatch_api as civicpatch_api
from runners.governing_law_collector import converters, fetchers, finders
from runners.governing_law_collector.schemas import GoverningLawCollectorContext, GoverningLawCollectorState, GoverningLawCollectorStep
from shared.schemas import GoverningLaw, GoverningLawKind, PipelineRunLimits
from shared.utils.statuses import PipelineRunStatus
from utils import cost_utils
from utils.log_utils import PipelineRunLogger

Step = tuple[GoverningLawCollectorContext, GoverningLawCollectorState]


def _next(context: GoverningLawCollectorContext, **data_updates) -> GoverningLawCollectorContext:
    return context.model_copy(update={"data": context.data.model_copy(update=data_updates)})


def _after_url(context: GoverningLawCollectorContext, **data_updates) -> Step:
    """Done with the url in hand: the next one, or classify what was stored."""
    remaining = context.data.pending_urls[1:]
    next_context = _next(context, pending_urls=remaining, fetched=None, markdown=None, escalate=False, **data_updates)
    return next_context, GoverningLawCollectorStep.FETCH_SOURCE if remaining else GoverningLawCollectorStep.CLASSIFY


async def start(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, GoverningLawCollectorStep.FIND_SOURCE


async def find_source(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    answer = await finders.find(context.data.config)
    logger.info(f"{answer.finder}: {answer.kind}, {len(answer.urls)} url(s)")
    next_context = _next(context, answer=answer, pending_urls=answer.urls)
    return next_context, GoverningLawCollectorStep.FETCH_SOURCE if answer.urls else GoverningLawCollectorStep.WRITE_GOVERNING_LAW


async def fetch_source(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    url = context.data.pending_urls[0]
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
    stored = await civicpatch_api.store_governing_law_source_page(
        client, context.data.jurisdiction_ocdid, context.data.pending_urls[0], markdown
    )
    return _after_url(context, source_page_ids=[*context.data.source_page_ids, stored["id"]])


async def classify(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, GoverningLawCollectorStep.WRITE_GOVERNING_LAW


async def write_governing_law(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, client: httpx.AsyncClient) -> Step:
    governing_law = governing_law_from(context)
    await civicpatch_api.put_governing_law(client, context.data.jurisdiction_ocdid, governing_law)
    return _next(context, governing_law=governing_law), PipelineRunStatus.SUCCESS


async def send_error(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, PipelineRunStatus.ERROR


def governing_law_from(context: GoverningLawCollectorContext) -> GoverningLaw:
    """What the run found. Urls it was told of but could not store leave it none found."""
    answer = context.data.answer
    assert answer is not None, "FIND_SOURCE always answers before WRITE_GOVERNING_LAW"
    stored = context.data.source_page_ids
    return GoverningLaw(
        kind=answer.kind if stored or not answer.urls else GoverningLawKind.NONE_FOUND,
        classification=answer.classification,
        finder=answer.finder,
        source_page_ids=stored,
        collected_at=datetime.now(timezone.utc),
        cost_usd=cost_utils.total_cost(context.pipeline_run_id),
    )


TRANSITION_MAP = {
    PipelineRunStatus.INIT: start,
    GoverningLawCollectorStep.FIND_SOURCE: find_source,
    GoverningLawCollectorStep.FETCH_SOURCE: fetch_source,
    GoverningLawCollectorStep.PREPROCESS_PAGE_CONTENT: preprocess_page_content,
    GoverningLawCollectorStep.STORE_SOURCE_PAGE: store_source_page,
    GoverningLawCollectorStep.CLASSIFY: classify,
    GoverningLawCollectorStep.WRITE_GOVERNING_LAW: write_governing_law,
    PipelineRunStatus.SEND_ERROR: send_error,
}
