"""A search for one kind of law, the target: grounded Gemini names starting points, and one crawl
takes them and the place's own site under a budget, keeping each page that passes the page test."""

from typing import List, Optional

import services.google_gemini.llm as gemini
import services.google_gemini.prompts as gemini_prompts
from .. import fetchers
from ..schemas import LawTarget, LawUrl, SearchResult, TriedReason, TriedUrl
from shared.utils.run_reports import BLOCKED_REASONS
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
    crawled = await crawl.crawl(url, named, target, page_test, fetchers.fetch_plain_first)
    tried = [unread for unread in crawled.unread if is_reported(unread, named, url, target)]
    logger.info(f"law search: {len(crawled.found)} {target.kind} url(s) from {len(named)} named by the model, {len(tried)} tried without reading")
    not_the_target = [TriedUrl(url=missed, reason=TriedReason.NOT_THE_TARGET) for missed in crawled.missed]
    site_crawled = [TriedUrl(url=url, reason=TriedReason.SITE_CRAWLED)] if url and not crawled.found else []
    law_urls = [LawUrl(url=page.url, kind=target.kind, markdown=page.markdown) for page in crawled.found]
    return SearchResult(law_urls=law_urls, tried=[*tried, *not_the_target, *site_crawled])


def is_reported(unread: TriedUrl, named: List[str], site: Optional[str], target: LawTarget) -> bool:
    """A blocked link that may be the law, or any url the model named that could not be read."""
    if unread.reason in BLOCKED_REASONS:
        return is_law_link(unread.url, named, site, target)
    return unread.url in named


def is_law_link(link: str, named: List[str], site: Optional[str], target: LawTarget) -> bool:
    """A starting point the model named, the place's home page (refused, it says the whole site is), or a link
    naming the law on the place's site or a publisher's: not a share button, whose url carries the page's own
    address and so names it too."""
    if link in named or (site is not None and link.rstrip("/") == site.rstrip("/")):
        return True
    on_site_or_publisher = fetchers.is_publisher(link) or (site is not None and crawl.on_site(link, site))
    return on_site_or_publisher and crawl.url_names_target(link, target)


async def _named_by_model(target: LawTarget, name: str, url: Optional[str], pipeline_run_id: str, jurisdiction_ocdid: str, logger: PipelineRunLogger) -> List[str]:
    """Gemini often answers a grounding redirect, which the fetch follows."""
    prompt = gemini_prompts.law_search_prompt(jurisdiction_ocdid, name, target.kind, target.description, target.terms, url)
    try:
        answer = await gemini.run_prompt(pipeline_run_id, jurisdiction_ocdid, prompt, prompt_name=PROMPT_NAME)
    except (RuntimeError, ValueError) as error:  # every model refused, or none answered JSON: a miss, not the run's end
        logger.warning(f"law search: no answer from the model, {type(error).__name__}: {error}")
        return []
    return [candidate for candidate in answer.get(URLS_KEY) or [] if isinstance(candidate, str)]
