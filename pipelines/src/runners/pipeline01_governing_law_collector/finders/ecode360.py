"""A link into a code on eCode360 becomes the print page of the law the search wants. Main-text
extraction finds only a cookie banner on its ordinary pages, and the law sits several clicks down:
`/toc/{code}` answers the whole tree as JSON, and `/print/{code}?guid=` a whole title on one page."""

import json
import re
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from ..converters.ecode360 import HOST, PRINT_PATH, is_print_page
from ..schemas import FetchedPage, LawTarget

BASE_URL = f"https://{HOST}"
TOC_PATH = "/toc/"
_CODE = re.compile(r"^[A-Z]{2}\d{4}$")
_TITLE_KEYS = ("title", "tocName")

Fetch = Callable[[str], Awaitable[Optional[FetchedPage]]]


def is_on_ecode360(url: str) -> bool:
    return urlparse(url).netloc.lower().removeprefix("www.") == HOST


def code_of(page: FetchedPage) -> Optional[str]:
    """The code's id: in the url of its contents page, and a class on every page's body."""
    first_segment = urlparse(page.url).path.strip("/").split("/")[0]
    if _CODE.match(first_segment):
        return first_segment
    body = BeautifulSoup(page.body, "html.parser").body
    classes = body.get("class") if body else None
    return next((name for name in classes or [] if _CODE.match(str(name))), None)


def _names_target(node: Dict[str, Any], target: LawTarget) -> bool:
    words = " ".join(str(node.get(key) or "") for key in _TITLE_KEYS).lower()
    return any(term.lower() in words for term in target.terms) and not any(word in words for word in target.skip_words)


def law_guid(toc: Dict[str, Any], target: LawTarget) -> Optional[str]:
    """The top-level part naming the target. A division holding one title prints as that title."""
    node = next((child for child in toc.get("children") or [] if _names_target(child, target)), None)
    if node is None:
        return None
    while len(node.get("children") or []) == 1:
        node = node["children"][0]
    return node.get("guid")


async def resolved(page: FetchedPage, target: LawTarget, fetch: Fetch) -> FetchedPage:
    """The law's print page, or the page as it came when this is no way into a code holding it."""
    if not is_on_ecode360(page.url) or is_print_page(page.url):
        return page
    code = code_of(page)
    if code is None:
        return page
    toc_page = await fetch(f"{BASE_URL}{TOC_PATH}{code}")
    if toc_page is None:
        return page
    try:
        guid = law_guid(json.loads(toc_page.body), target)
    except ValueError:
        return page
    if guid is None:
        return page
    printed = await fetch(f"{BASE_URL}{PRINT_PATH}{code}?guid={guid}")
    return printed or page
