"""A place's own site searched for its charter under a budget: sitemap entries naming one, then
every link on the site one hop out, then only charter-named links for two hops more. Pure parts
take bytes; `crawl` takes the fetch."""

import re
from typing import Awaitable, Callable, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from ..schemas import FetchedPage
from . import confirm
from .. import converters

MAX_PAGES = 60
MAX_SITEMAPS = 6
MAX_DEPTH = 3
# A page the sitemap names counts as one hop from home: its links are followed charter-named only.
SITEMAP_PAGE_DEPTH = 1
CHARTER_LINK_WORD = "charter"
# A "charter school" link is never the government's charter.
SKIP_LINK_WORD = "school"
SITEMAP_PATH = "/sitemap.xml"
ROBOTS_PATH = "/robots.txt"
_ROBOTS_SITEMAP = re.compile(r"^sitemap:\s*(\S+)", re.IGNORECASE | re.MULTILINE)
_SITEMAP_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>")
_SITEMAP_INDEX = "<sitemapindex"

# None when the url refused, failed or timed out: the crawl moves on.
Fetch = Callable[[str], Awaitable[Optional[FetchedPage]]]


def site_host(url: str) -> str:
    return re.sub(r"^www\.", "", urlparse(url).netloc.lower())


def on_site(url: str, site: str) -> bool:
    """The site itself or one of its subdomains: Benton County's charter is on counsel.bentoncountyor.gov."""
    host, site_host_name = site_host(url), site_host(site)
    return host == site_host_name or host.endswith("." + site_host_name)


def links(html: bytes, base: str, site: str, *, charter_named_only: bool) -> List[str]:
    """Charter-named links first, so the budget goes to the likely pages."""
    found: List[str] = []
    for anchor in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        text = f"{anchor.get_text(' ', strip=True)} {anchor['href']}".lower()
        url = urljoin(base, str(anchor["href"]).split("#")[0])
        if not url.startswith("http") or url in found or SKIP_LINK_WORD in text:
            continue
        if charter_named_only and CHARTER_LINK_WORD not in text:
            continue
        if not charter_named_only and not on_site(url, site):
            continue
        found.append(url)
    return sorted(found, key=lambda link: not names_a_charter(link))


def sitemap_urls(robots: bytes) -> List[str]:
    return _ROBOTS_SITEMAP.findall(robots.decode(errors="ignore"))


def sitemap_entries(body: bytes) -> tuple[bool, List[str]]:
    """Whether this sitemap lists other sitemaps, and its entries."""
    text = body.decode(errors="ignore")
    return _SITEMAP_INDEX in text, _SITEMAP_LOC.findall(text)


def names_a_charter(url: str) -> bool:
    lowered = url.lower()
    return CHARTER_LINK_WORD in lowered and SKIP_LINK_WORD not in lowered


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


async def crawl(site: str, name: str, charter_terms: List[str], fetch: Fetch) -> List[str]:
    """The first charter url confirmed on the site, as a one-element list; empty when the budget
    runs out first. One charter is all a place has, so the crawl stops at it."""
    budget = Budget()
    seen: set[str] = set()
    frontier: List[tuple[str, int]] = []
    for url in await _sitemap_charter_urls(site, fetch, budget):
        if budget.spent():
            break
        page = await _fetch(url, fetch, budget, seen)
        if page is None:
            continue
        if _is_charter(page, name, charter_terms):
            return [page.url]
        if _is_html(page):
            frontier.extend((link, SITEMAP_PAGE_DEPTH + 1) for link in links(page.body, page.url, site, charter_named_only=True))
    return await _walk([*frontier, (site, 0)], site, name, charter_terms, fetch, budget, seen)


async def _walk(
    frontier: List[tuple[str, int]], site: str, name: str, charter_terms: List[str], fetch: Fetch, budget: Budget, seen: set[str]
) -> List[str]:
    """Breadth first from the frontier, charter-named links ahead, until a charter or the budget."""
    while frontier and not budget.spent():
        url, depth = frontier.pop(0)
        if url in seen:
            continue
        page = await _fetch(url, fetch, budget, seen)
        if page is None:
            continue
        if depth > 0 and _is_charter(page, name, charter_terms):
            return [page.url]
        if depth < MAX_DEPTH and _is_html(page):
            new = [(link, depth + 1) for link in links(page.body, page.url, site, charter_named_only=depth > 0) if link not in seen]
            frontier = sorted([*frontier, *new], key=lambda item: not names_a_charter(item[0]))
    return []


async def _sitemap_charter_urls(site: str, fetch: Fetch, budget: Budget) -> List[str]:
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
            found.extend(entry for entry in entries if names_a_charter(entry))
    return found


async def _fetch(url: str, fetch: Fetch, budget: Budget, seen: set[str]) -> Optional[FetchedPage]:
    seen.add(url)
    budget.pages += 1
    return await fetch(url)


def _is_html(page: FetchedPage) -> bool:
    return "html" in page.content_type


def _is_charter(page: FetchedPage, name: str, charter_terms: List[str]) -> bool:
    markdown = markdown_of(page)
    return markdown is not None and confirm.is_charter(markdown, name, charter_terms)
