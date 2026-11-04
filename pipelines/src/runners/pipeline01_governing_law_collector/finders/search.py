"""A search for one kind of law, the target: grounded Gemini is asked for its url, each answer kept
only when the fetched page passes the target's page test; the place's own site is then crawled
under a budget for the rest of it."""

from typing import List, Optional

import httpx
import services.google_gemini.llm as gemini
import services.google_gemini.prompts as gemini_prompts
from ..fetchers import plain
from ..schemas import FetchedPage, LawTarget, SearchResult, TriedReason, TriedUrl, as_law_urls
from . import crawl
from utils.log_utils import PipelineRunLogger

PROMPT_NAME = "law_search"
URLS_KEY = "urls"


async def find(
    target: LawTarget, page_test: crawl.PageTest, name: str, url: Optional[str], pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger
) -> SearchResult:
    """A state with no word for the target has nothing to search for."""
    if not target.terms:
        return SearchResult()
    urls, tried = await _by_model(target, page_test, name, url, pipeline_run_id, jurisdiction_ocdid, logger)
    if url:
        crawled = await crawl.crawl(url, target, page_test, _fetch)
        logger.info(f"site crawl: {len(crawled)} {target.kind} url(s)")
        urls = list(dict.fromkeys([*urls, *crawled]))
        if not urls:
            tried = [*tried, TriedUrl(url=url, reason=TriedReason.SITE_CRAWLED)]
    return SearchResult(law_urls=as_law_urls(urls, target.kind), tried=tried)


async def _by_model(
    target: LawTarget, page_test: crawl.PageTest, name: str, url: Optional[str], pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger
) -> tuple[List[str], List[TriedUrl]]:
    """The urls Gemini named that fetch and pass, each as its final url, and the rest with why not.
    Gemini often answers a grounding redirect, which `plain.fetch` follows."""
    prompt = gemini_prompts.law_search_prompt(jurisdiction_ocdid, name, target.kind, target.description, target.terms, url)
    try:
        answer = await gemini.run_prompt(pipeline_run_id, jurisdiction_ocdid, prompt, prompt_name=PROMPT_NAME)
    except (RuntimeError, ValueError) as error:  # every model refused, or none answered JSON: a miss, not the run's end
        logger.warning(f"law search: no answer from the model, {type(error).__name__}: {error}")
        return [], []
    named = [candidate for candidate in answer.get(URLS_KEY) or [] if isinstance(candidate, str)]
    confirmed: List[str] = []
    tried: List[TriedUrl] = []
    for candidate in named:
        outcome = await _confirmed_or_tried(candidate, page_test)
        if isinstance(outcome, TriedUrl):
            tried.append(outcome)
        else:
            confirmed.append(outcome)
    logger.info(f"law search: the model named {len(named)} {target.kind} url(s), {len(confirmed)} confirmed")
    return confirmed, tried


async def _confirmed_or_tried(candidate: str, page_test: crawl.PageTest) -> str | TriedUrl:
    """The candidate's final url when its page passes, else the candidate and why not."""
    try:
        page = await plain.fetch(candidate)
    except plain.RefusedByHost:
        return TriedUrl(url=candidate, reason=TriedReason.REFUSED)
    except plain.OffLimits:
        return TriedUrl(url=candidate, reason=TriedReason.OFF_LIMITS)
    except httpx.HTTPError:
        return TriedUrl(url=candidate, reason=TriedReason.FAILED)
    markdown = crawl.markdown_of(page)
    if markdown is not None and await page_test(markdown, page.url):
        return page.url
    return TriedUrl(url=page.url, reason=TriedReason.NOT_THE_TARGET)


async def _fetch(url: str) -> Optional[FetchedPage]:
    try:
        return await plain.fetch(url)
    except (plain.RefusedByHost, plain.OffLimits, httpx.HTTPError):
        return None
