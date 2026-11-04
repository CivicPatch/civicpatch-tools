"""A place's own site searched for a target under a budget: sitemap entries naming it, then every
link on the site one hop out, then only links naming it for two hops more. Pure parts take bytes;
`crawl` takes the fetch and the page test."""

import re
from typing import Awaitable, Callable, List, Optional
from urllib.parse import urljoin, urlparse

from utils.page_links import PageLink, page_links
from ..schemas import FetchedPage, LawTarget
from .. import converters

MAX_PAGES = 60
MAX_SITEMAPS = 6
MAX_DEPTH = 3
# A page the sitemap names counts as one hop from home: only its links naming the target are followed.
SITEMAP_PAGE_DEPTH = 1
# Google Translate's copy of a site: Washington County's menu gave eleven of one page.
TRANSLATE_PROXY_HOST = ".translate.goog"
SITEMAP_PATH = "/sitemap.xml"
ROBOTS_PATH = "/robots.txt"
_ROBOTS_SITEMAP = re.compile(r"^sitemap:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
_SITEMAP_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_SITEMAP_INDEX = "<sitemapindex"

# None when the url refused, failed or timed out: the crawl moves on.
Fetch = Callable[[str], Awaitable[Optional[FetchedPage]]]
# Whether a page's markdown, at this url, is what is searched for.
PageTest = Callable[[str, str], Awaitable[bool]]


def site_host(url: str) -> str:
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower())


def on_site(url: str, site: str) -> bool:
    """The site itself or one of its subdomains: Benton County's charter is on counsel.bentoncountyor.gov."""
    host, site_host_name = site_host(url), site_host(site)
    return host == site_host_name or host.endswith("." + site_host_name)


def links(html: bytes, base: str, site: str, target: LawTarget, *, named_only: bool) -> List[PageLink]:
    """Links naming the target first, so the budget goes to the likely pages."""
    found: List[PageLink] = []
    for link in page_links(html, base):
        if _has_skip_word(_link_words(link), target) or urlparse(link.url).netloc.endswith(TRANSLATE_PROXY_HOST):
            continue
        if named_only and not link_names_target(link, target):
            continue
        if not named_only and not on_site(link.url, site):
            continue
        found.append(link)
    return sorted(found, key=lambda link: not link_names_target(link, target))


def sitemap_urls(robots: bytes) -> List[str]:
    return _ROBOTS_SITEMAP.findall(robots.decode(errors="ignore"))


def sitemap_entries(body: bytes) -> tuple[bool, List[str]]:
    """Whether this sitemap lists other sitemaps, and its entries."""
    text = body.decode(errors="ignore")
    return _SITEMAP_INDEX in text, _SITEMAP_LOC.findall(text)


def _url_words(url: str) -> str:
    """Path and query, not the host: every link on schoolcraftcounty.net would read as a school."""
    parsed = urlparse(url)
    return f"{parsed.path} {parsed.query}".lower()


def _link_words(link: PageLink) -> str:
    return f"{link.text.lower()} {_url_words(link.url)}"


def _has_skip_word(words: str, target: LawTarget) -> bool:
    return any(word in words for word in target.skip_words)


def _names_target(words: str, target: LawTarget) -> bool:
    return any(term.lower() in words for term in target.terms) and not _has_skip_word(words, target)


def link_names_target(link: PageLink, target: LawTarget) -> bool:
    return _names_target(_link_words(link), target)


def markdown_of(page: FetchedPage) -> Optional[str]:
    try:
        return converters.to_markdown(page)
    except converters.UnsupportedContentType:
        return None


class Budget:
    """Pages fetched so far; the crawl stops at MAX_PAGES."""

    def __init__(self) -> None:
        self.pages = 0

    def spent(self) -> bool:
        return self.pages >= MAX_PAGES


async def crawl(site: str, target: LawTarget, page_test: PageTest, fetch: Fetch) -> List[str]:
    """Every url on the site that passes the page test, within the budget: a law can span several
    pages and its amendments others, so a hit never ends the crawl."""

    async def is_hit(page: FetchedPage) -> bool:
        markdown = markdown_of(page)
        return markdown is not None and await page_test(markdown, page.url)

    budget = Budget()
    seen: set[str] = set()
    frontier: List[tuple[PageLink, int]] = []
    found: List[str] = []
    for url in await _sitemap_target_urls(site, target, fetch, budget):
        if budget.spent():
            break
        page = await _fetch(url, fetch, budget, seen)
        if page is None:
            continue
        if await is_hit(page):
            found.append(page.url)
        if _is_html(page):
            frontier.extend((link, SITEMAP_PAGE_DEPTH + 1) for link in links(page.body, page.url, site, target, named_only=True))
    walked = await _walk([*frontier, (PageLink(url=site), 0)], site, target, is_hit, fetch, budget, seen)
    return list(dict.fromkeys([*found, *walked]))


async def _walk(
    frontier: List[tuple[PageLink, int]], site: str, target: LawTarget, is_hit: Callable[[FetchedPage], Awaitable[bool]], fetch: Fetch, budget: Budget, seen: set[str]
) -> List[str]:
    """Breadth first from the frontier, links naming the target ahead, until it empties or the budget."""
    found: List[str] = []
    while frontier and not budget.spent():
        link, depth = frontier.pop(0)
        if link.url in seen:
            continue
        page = await _fetch(link.url, fetch, budget, seen)
        if page is None:
            continue
        if depth > 0 and await is_hit(page):
            found.append(page.url)
        if depth < MAX_DEPTH and _is_html(page):
            on_page = links(page.body, page.url, site, target, named_only=depth > 0)
            new = [(on_page_link, depth + 1) for on_page_link in on_page if on_page_link.url not in seen]
            frontier = sorted([*frontier, *new], key=lambda item: not link_names_target(item[0], target))
    return found


async def _sitemap_target_urls(site: str, target: LawTarget, fetch: Fetch, budget: Budget) -> List[str]:
    robots = await fetch(urljoin(site, ROBOTS_PATH))
    budget.pages += 1
    queue = [*(sitemap_urls(robots.body) if robots else []), urljoin(site, SITEMAP_PATH)]
    found: List[str] = []
    read = 0
    while queue and read < MAX_SITEMAPS:
        page = await fetch(queue.pop(0))
        budget.pages += 1
        read += 1
        if page is None:
            continue
        is_index, entries = sitemap_entries(page.body)
        if is_index:
            queue.extend(entries)
        else:
            found.extend(entry for entry in entries if _names_target(_url_words(entry), target))
    return found


async def _fetch(url: str, fetch: Fetch, budget: Budget, seen: set[str]) -> Optional[FetchedPage]:
    seen.add(url)
    budget.pages += 1
    return await fetch(url)


def _is_html(page: FetchedPage) -> bool:
    return "html" in page.content_type
