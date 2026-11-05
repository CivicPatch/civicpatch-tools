"""A search for one kind of law, the target: grounded Gemini names starting points, and one crawl
takes them and the place's own site under a budget, keeping each page that passes the page test."""

from typing import List, Optional

import httpx
import services.google_gemini.llm as gemini
import services.google_gemini.prompts as gemini_prompts
from .. import fetchers
from ..fetchers import plain
from ..schemas import FetchedPage, LawTarget, LawUrl, SearchResult, TriedReason, TriedUrl
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
    named = await _named_by_model(target, name, url, pipeline_run_id, jurisdiction_ocdid, logger)
    tried: List[TriedUrl] = []

    async def fetch(link: str) -> Optional[FetchedPage]:
        try:
            return await fetchers.fetch_plain_first(link)
        except (plain.RefusedByHost, plain.DisallowedByRobots) as block:
            tried.append(TriedUrl(url=link, reason=_blocked_reason(block)))
        except plain.OffLimits:
            if link in named:
                tried.append(TriedUrl(url=link, reason=TriedReason.OFF_LIMITS))
        except httpx.HTTPError:
            if link in named:
                tried.append(TriedUrl(url=link, reason=TriedReason.FAILED))
        return None

    crawled = await crawl.crawl(url, named, target, page_test, fetch)
    logger.info(f"law search: {len(crawled.found)} {target.kind} url(s) from {len(named)} named by the model, {len(tried)} tried without reading")
    not_the_target = [TriedUrl(url=missed, reason=TriedReason.NOT_THE_TARGET) for missed in crawled.missed]
    site_crawled = [TriedUrl(url=url, reason=TriedReason.SITE_CRAWLED)] if url and not crawled.found else []
    law_urls = [LawUrl(url=page.url, kind=target.kind, markdown=page.markdown) for page in crawled.found]
    return SearchResult(law_urls=law_urls, tried=[*tried, *not_the_target, *site_crawled])


async def _named_by_model(target: LawTarget, name: str, url: Optional[str], pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger) -> List[str]:
    """Gemini often answers a grounding redirect, which the fetch follows."""
    prompt = gemini_prompts.law_search_prompt(jurisdiction_ocdid, name, target.kind, target.description, target.terms, url)
    try:
        answer = await gemini.run_prompt(pipeline_run_id, jurisdiction_ocdid, prompt, prompt_name=PROMPT_NAME)
    except (RuntimeError, ValueError) as error:  # every model refused, or none answered JSON: a miss, not the run's end
        logger.warning(f"law search: no answer from the model, {type(error).__name__}: {error}")
        return []
    return [candidate for candidate in answer.get(URLS_KEY) or [] if isinstance(candidate, str)]


def _blocked_reason(block: plain.RefusedByHost | plain.DisallowedByRobots) -> TriedReason:
    if isinstance(block, plain.DisallowedByRobots):
        return TriedReason.DISALLOWED_BY_ROBOTS
    return TriedReason.CHALLENGED if block.challenged else TriedReason.REFUSED
