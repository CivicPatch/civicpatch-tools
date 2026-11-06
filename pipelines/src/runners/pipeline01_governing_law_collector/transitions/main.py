"""One handler per state of GOVERNING_LAW_COLLECTOR_TRANSITIONS. Each takes the context and
answers it with the next state; the engine checks the answer against the graph."""

from datetime import datetime, timezone
from typing import List, Optional

import httpx
import services.civicpatch_api as civicpatch_api
from runners.pipeline01_governing_law_collector import converters, fetchers, finders
from ..schemas import FinderAnswer, GoverningLawCollectorContext, GoverningLawCollectorState, GoverningLawCollectorStep, LawKind, LawUrl
from shared.schemas import GoverningLaw, GoverningLawKind, JurisdictionExtras, PipelineRunLimits
from shared.utils.layered_config import GovernedBy
from shared.utils.statuses import PipelineRunStatus
from utils import cost_utils
from utils.log_utils import PipelineRunLogger

Step = tuple[GoverningLawCollectorContext, GoverningLawCollectorState]


def _next(context: GoverningLawCollectorContext, **data_updates) -> GoverningLawCollectorContext:
    return context.model_copy(update={"data": context.data.model_copy(update=data_updates)})


async def start(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, GoverningLawCollectorStep.FIND_SOURCES


async def find_sources(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    answer = await finders.find(context.data.config, context.pipeline_run_id, context.data.jurisdiction_ocdid, logger)
    logger.info(f"{answer.found_by}: {len(answer.urls_of(LawKind.CHARTER))} charter url(s), {len(answer.urls_of(LawKind.STATUTE))} general law url(s)")
    return _next(context, answer=answer, governed_by=_governed_by(context, answer)), GoverningLawCollectorStep.STORE_SOURCES


def _governed_by(context: GoverningLawCollectorContext, answer: FinderAnswer) -> Optional[GovernedBy]:
    governing_law = context.data.config.governing_law
    if governing_law is None or answer.classification is None:
        return None
    classification = governing_law.classifications.get(answer.classification)
    return classification.governed_by if classification else None


async def store_sources(_limits: PipelineRunLimits, logger: PipelineRunLogger, context: GoverningLawCollectorContext, client: httpx.AsyncClient) -> Step:
    answer = context.data.answer
    assert answer is not None, "FIND_SOURCES always answers before STORE_SOURCES"
    charter: List[str] = []
    general_law: List[str] = []
    skipped: List[str] = []
    for law_url in answer.law_urls:
        source_page_id = await _source_page_id(client, context.data.jurisdiction_ocdid, law_url, logger)
        if source_page_id is None:
            skipped.append(law_url.url)
        elif law_url.kind == LawKind.CHARTER:
            charter.append(source_page_id)
        else:
            general_law.append(source_page_id)
    next_context = _next(context, charter_source_page_ids=charter, general_law_source_page_ids=general_law, skipped_urls=skipped)
    return next_context, GoverningLawCollectorStep.WRITE_GOVERNING_LAW


async def _source_page_id(client: httpx.AsyncClient, jurisdiction_ocdid: str, law_url: LawUrl, logger: PipelineRunLogger) -> Optional[str]:
    """Text a search already read is stored as it is. Any other url is reused if another run stored
    it within a day, else fetched. None when it could not be read."""
    markdown = law_url.markdown
    if markdown is None:
        reused = await civicpatch_api.reuse_governing_law_source_page(client, jurisdiction_ocdid, law_url.url)
        if reused is not None:
            logger.info(f"{law_url.url}: stored by another run within a day, not fetched again")
            return reused["id"]
        markdown = await _read(law_url.url, logger)
    if markdown is None:
        return None
    stored = await civicpatch_api.store_governing_law_source_page(client, jurisdiction_ocdid, law_url.url, markdown)
    return stored["id"]


async def _read(url: str, logger: PipelineRunLogger) -> Optional[str]:
    markdown = await _read_once(url, logger, by_browser=False)
    if markdown is None or not converters.is_nearly_empty(markdown):
        return markdown
    logger.info(f"{url}: nearly empty by plain GET, fetching again by browser")
    markdown = await _read_once(url, logger, by_browser=True)
    if markdown is not None and converters.is_nearly_empty(markdown):
        logger.warning(f"{url}: nearly empty even by browser, skipped")
        return None
    return markdown


async def _read_once(url: str, logger: PipelineRunLogger, *, by_browser: bool) -> Optional[str]:
    try:
        return converters.to_markdown(await fetchers.fetch(url, by_browser=by_browser))
    except fetchers.RefusedByHost as refused:
        logger.warning(f"{url}: refused with {refused.status_code}, not retried")
    except fetchers.OffLimits as off_limits:
        logger.warning(f"{off_limits}; skipped")
    except httpx.HTTPError as error:
        logger.warning(f"{url}: failed, {type(error).__name__}: {error}; skipped")
    except converters.UnsupportedContentType as unsupported:
        logger.warning(f"{unsupported}; skipped")
    return None


async def write_governing_law(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, client: httpx.AsyncClient) -> Step:
    governing_law = governing_law_from(context)
    await civicpatch_api.patch_jurisdiction_extras(
        client, context.data.jurisdiction_ocdid, JurisdictionExtras(extras_governing_law=governing_law)
    )
    # A miss is not a failed run: cp.org files its issue from the context the engine sends.
    return _next(context, governing_law=governing_law), PipelineRunStatus.SUCCESS


async def send_error(_limits: PipelineRunLimits, _logger: PipelineRunLogger, context: GoverningLawCollectorContext, _client: httpx.AsyncClient) -> Step:
    return context, PipelineRunStatus.ERROR


def governing_law_from(context: GoverningLawCollectorContext) -> GoverningLaw:
    """What the run stored decides the kind, not what the finder hoped for: a charter if one was
    stored, else general law if a statute was, else none found."""
    answer = context.data.answer
    assert answer is not None, "FIND_SOURCES always answers before WRITE_GOVERNING_LAW"
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
    GoverningLawCollectorStep.FIND_SOURCES: find_sources,
    GoverningLawCollectorStep.STORE_SOURCES: store_sources,
    GoverningLawCollectorStep.WRITE_GOVERNING_LAW: write_governing_law,
    PipelineRunStatus.SEND_ERROR: send_error,
}
