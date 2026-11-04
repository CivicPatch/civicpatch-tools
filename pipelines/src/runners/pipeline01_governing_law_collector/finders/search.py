"""Where a state keeps no charter index: grounded Gemini is asked for the place's charter url,
each answer kept only when the fetched page is the charter; failing that, the place's own site
is crawled under a budget. The statutes stay the classification's."""

from typing import List, Optional

import httpx
import services.google_gemini.llm as gemini
import services.google_gemini.prompts as gemini_prompts
from ..fetchers import plain
from ..schemas import FetchedPage, FinderAnswer, TriedReason, TriedUrl
from . import confirm, crawl
from shared.schemas import FoundBy
from shared.utils.layered_config import GoverningLawConfig, resolve_classification
from utils.log_utils import PipelineRunLogger

PROMPT_NAME = "charter_search"
CHARTER_URLS_KEY = "charter_urls"


async def find(
    governing_law: GoverningLawConfig, name: str, url: Optional[str], pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger
) -> FinderAnswer:
    classification_id = resolve_classification(governing_law, name, None)
    general_law_urls = governing_law.classifications[classification_id].general_law if classification_id else []
    charter_urls, tried = await _by_model(governing_law, name, url, pipeline_run_id, jurisdiction_ocdid, logger)
    if not charter_urls and url:
        charter_urls = await crawl.crawl(url, name, governing_law.charter_terms, _fetch)
        logger.info(f"site crawl: {len(charter_urls)} charter url(s)")
        if not charter_urls:
            tried = [*tried, TriedUrl(url=url, reason=TriedReason.SITE_CRAWLED)]
    return FinderAnswer(
        found_by=FoundBy.SEARCH, classification=classification_id, charter_urls=charter_urls, general_law_urls=general_law_urls, tried=tried
    )


async def _by_model(
    governing_law: GoverningLawConfig, name: str, url: Optional[str], pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger
) -> tuple[List[str], List[TriedUrl]]:
    """The urls Gemini named that fetch and are the charter, each as its final url, and the rest
    with why not. Gemini often answers a grounding redirect, which `plain.fetch` follows."""
    prompt = gemini_prompts.charter_search_prompt(jurisdiction_ocdid, name, governing_law.charter_terms, url)
    try:
        answer = await gemini.run_prompt(pipeline_run_id, jurisdiction_ocdid, prompt, prompt_name=PROMPT_NAME)
    except (RuntimeError, ValueError) as error:  # every model refused, or none answered JSON: a miss, not the run's end
        logger.warning(f"charter search: no answer from the model, {type(error).__name__}: {error}")
        return [], []
    named = [candidate for candidate in answer.get(CHARTER_URLS_KEY) or [] if isinstance(candidate, str)]
    confirmed: List[str] = []
    tried: List[TriedUrl] = []
    for candidate in named:
        outcome = await _confirmed_or_tried(candidate, name, governing_law.charter_terms)
        if isinstance(outcome, TriedUrl):
            tried.append(outcome)
        else:
            confirmed.append(outcome)
    logger.info(f"charter search: the model named {len(named)} url(s), {len(confirmed)} confirmed")
    return confirmed, tried


async def _confirmed_or_tried(candidate: str, name: str, charter_terms: List[str]) -> str | TriedUrl:
    """The candidate's final url when its page is the charter, else the candidate and why not."""
    try:
        page = await plain.fetch(candidate)
    except plain.RefusedByHost:
        return TriedUrl(url=candidate, reason=TriedReason.REFUSED)
    except plain.OffLimits:
        return TriedUrl(url=candidate, reason=TriedReason.OFF_LIMITS)
    except httpx.HTTPError:
        return TriedUrl(url=candidate, reason=TriedReason.FAILED)
    markdown = crawl.markdown_of(page)
    if markdown is not None and confirm.is_charter(markdown, name, charter_terms):
        return page.url
    return TriedUrl(url=page.url, reason=TriedReason.NOT_A_CHARTER)


async def _fetch(url: str) -> Optional[FetchedPage]:
    try:
        return await plain.fetch(url)
    except (plain.RefusedByHost, plain.OffLimits, httpx.HTTPError):
        return None
