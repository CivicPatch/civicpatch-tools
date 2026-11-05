"""A link into a code on Municode becomes the page of the law the search wants: a code's contents
list each part by name, at a `nodeId` that differs from code to code (CHTR, CHCA, CICH)."""

from typing import List, Optional
from urllib.parse import parse_qs, urlparse

from utils.page_links import PageLink, page_links
from .ecode360 import Fetch
from ..schemas import FetchedPage, LawTarget

HOST = "municode.com"
NODE_ID = "nodeId"


def is_on_municode(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host == HOST or host.endswith("." + HOST)


def node_of(url: str) -> Optional[str]:
    return next(iter(parse_qs(urlparse(url).query).get(NODE_ID, [])), None)


def _names_target(link: PageLink, target: LawTarget) -> bool:
    words = link.text.lower()
    return any(term.lower() in words for term in target.terms) and not any(word in words for word in target.skip_words)


def law_link(links: List[PageLink], target: LawTarget) -> Optional[PageLink]:
    """The first part naming the target, or the part inside it: Washington County's CH is only a
    heading over CH01, which holds the charter."""
    named = [link for link in links if node_of(link.url) and _names_target(link, target)]
    if not named:
        return None
    parent = named[0]
    parent_node = node_of(parent.url) or ""
    return next((link for link in named[1:] if (node_of(link.url) or "").startswith(parent_node)), parent)


async def resolved(page: FetchedPage, target: LawTarget, fetch: Fetch) -> FetchedPage:
    """The law's page, or the page as it came when this is no way into a code holding it."""
    if not is_on_municode(page.url):
        return page
    link = law_link(page_links(page.body, page.url), target)
    if link is None or node_of(link.url) == node_of(page.url):
        return page
    return await fetch(link.url) or page
