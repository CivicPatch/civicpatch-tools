"""A search for a target under a budget: the starting points it was given, sitemap entries naming it,
then every link on the site one hop out, then only links naming it for two hops more. Pure parts take
bytes; `crawl` takes the fetch and the page test."""

import re
from typing import Awaitable, Callable, List, Optional
from urllib.parse import urljoin, urlparse

from pydantic import BaseModel, ConfigDict
from utils.page_links import PageLink, page_links
from ..schemas import FetchedPage, LawTarget, ReadPage
from . import publishers
from .. import converters, fetchers

MAX_PAGES = 60
MAX_SITEMAPS = 6
MAX_DEPTH = 3
# A page named outright, by the sitemap or a starting point, counts as one hop from home: only its
# links naming the target are followed.
NAMED_PAGE_DEPTH = 1
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
    """Links naming the target and ways into a publisher first, so the budget goes to the likely pages."""
    found: List[PageLink] = []
    # A publisher's own links stay out: its handler picks the one part wanted from dozens.
    into_publisher = not fetchers.is_publisher(base)
    for link in page_links(html, base):
        if _has_skip_word(_link_words(link), target) or urlparse(link.url).netloc.endswith(TRANSLATE_PROXY_HOST):
            continue
        if into_publisher and fetchers.is_publisher(link.url):
            found.append(link)
            continue
        if named_only and not link_names_target(link, target):
            continue
        # A home page often links its charter straight on a publisher's host.
        if not named_only and not on_site(link.url, site) and not link_names_target(link, target):
            continue
        found.append(link)
    return sorted(found, key=lambda link: not _is_likely(link, target))


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


def _is_likely(link: PageLink, target: LawTarget) -> bool:
    return link_names_target(link, target) or fetchers.is_publisher(link.url)


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


class Crawled(BaseModel):
    model_config = ConfigDict(frozen=True)

    found: List[ReadPage]
    # Starting points that fetched but did not pass the page test.
    missed: List[str]


class _Visited(BaseModel):
    model_config = ConfigDict(frozen=True)

    fetched: List[str]
    hits: List[ReadPage]
    frontier: List[tuple[PageLink, int]]


async def crawl(site: Optional[str], starting_points: List[str], target: LawTarget, page_test: PageTest, fetch: Fetch) -> Crawled:
    """Every page that passes the page test, within the budget: a law can span several pages and its
    amendments others, so a hit never ends the crawl. With no site, the first starting point that
    fetches off a publisher's host stands for it."""
    budget = Budget()
    seen: set[str] = set()
    started = await _visit(starting_points, site or "", target, page_test, fetch, budget, seen)
    hit_urls = {hit.url for hit in started.hits}
    missed = [url for url in started.fetched if url not in hit_urls]
    home = site or _home_of(started.fetched)
    if home is None:
        return Crawled(found=started.hits, missed=missed)
    mapped = await _visit(await _sitemap_target_urls(home, target, fetch, budget), home, target, page_test, fetch, budget, seen)
    # A starting point may be the home page itself, whose links are still to be walked.
    seen.discard(home)
    walked = await _walk([*started.frontier, *mapped.frontier, (PageLink(url=home), 0)], home, target, page_test, fetch, budget, seen)
    return Crawled(found=_one_per_url([*started.hits, *mapped.hits, *walked]), missed=missed)


def _home_of(urls: List[str]) -> Optional[str]:
    parsed = next((urlparse(url) for url in urls if not fetchers.is_publisher(url)), None)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed else None


def _one_per_url(pages: List[ReadPage]) -> List[ReadPage]:
    by_url: dict[str, ReadPage] = {}
    for page in pages:
        by_url.setdefault(page.url, page)
    return list(by_url.values())


async def _hit(page: FetchedPage, page_test: PageTest) -> Optional[ReadPage]:
    markdown = markdown_of(page)
    if markdown is not None and await page_test(markdown, page.url):
        return ReadPage(url=page.url, markdown=markdown)
    return None


async def _visit(urls: List[str], site: str, target: LawTarget, page_test: PageTest, fetch: Fetch, budget: Budget, seen: set[str]) -> _Visited:
    """Pages named outright: each is tested, and its links naming the target join the frontier."""
    fetched: List[str] = []
    hits: List[ReadPage] = []
    frontier: List[tuple[PageLink, int]] = []
    for url in urls:
        if budget.spent():
            break
        if url in seen:
            continue
        page = await _fetch(url, target, fetch, budget, seen)
        if page is None:
            continue
        fetched.append(page.url)
        hit = await _hit(page, page_test)
        if hit:
            hits.append(hit)
        if _is_html(page):
            frontier.extend((link, NAMED_PAGE_DEPTH + 1) for link in links(page.body, page.url, site, target, named_only=True))
    return _Visited(fetched=fetched, hits=hits, frontier=frontier)


async def _walk(frontier: List[tuple[PageLink, int]], site: str, target: LawTarget, page_test: PageTest, fetch: Fetch, budget: Budget, seen: set[str]) -> List[ReadPage]:
    """Breadth first from the frontier, likely links ahead, until it empties or the budget."""
    found: List[ReadPage] = []
    while frontier and not budget.spent():
        link, depth = frontier.pop(0)
        if link.url in seen:
            continue
        page = await _fetch(link.url, target, fetch, budget, seen)
        if page is None:
            continue
        hit = await _hit(page, page_test) if depth > 0 else None
        if hit:
            found.append(hit)
        if depth < MAX_DEPTH and _is_html(page):
            on_page = links(page.body, page.url, site, target, named_only=depth > 0)
            new = [(on_page_link, depth + 1) for on_page_link in on_page if on_page_link.url not in seen]
            frontier = sorted([*frontier, *new], key=lambda item: not _is_likely(item[0], target))
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


async def _fetch(url: str, target: LawTarget, fetch: Fetch, budget: Budget, seen: set[str]) -> Optional[FetchedPage]:
    seen.add(url)
    budget.pages += 1
    page = await fetch(url)
    if page is None:
        return None
    resolved = await publishers.resolved(page, target, fetch)
    seen.add(resolved.url)
    return resolved


def _is_html(page: FetchedPage) -> bool:
    return "html" in page.content_type
