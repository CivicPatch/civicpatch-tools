"""Turning a url into raw bytes. A plain GET first; the browser when the plain page turned out nearly
empty, or when a law publisher answers 403. Every other refusal stands: no other way is tried."""

from http import HTTPStatus
from urllib.parse import urlparse

from . import browser, plain
from .plain import DisallowedByRobots, OffLimits, RefusedByHost
from ..schemas import FetchedPage

__all__ = ["OffLimits", "RefusedByHost", "fetch", "fetch_plain_first"]

PUBLISHER_HOSTS = (
    "amlegal.com",
    "codepublishing.com",
    "ecode360.com",
    "municipal.codes",
    "municipalcodeonline.com",
    "municode.com",
    "qcode.us",
    "sterlingcodifiers.com",
)


def is_publisher(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == publisher or host.endswith("." + publisher) for publisher in PUBLISHER_HOSTS)


async def fetch_plain_first(url: str) -> FetchedPage:
    try:
        return await plain.fetch(url)
    except RefusedByHost as refused:
        if refused.status_code != HTTPStatus.FORBIDDEN or not is_publisher(refused.url):
            raise
        return await browser.fetch(refused.url)


async def fetch(url: str, by_browser: bool) -> FetchedPage:
    if by_browser:
        return await browser.fetch(url)
    return await fetch_plain_first(url)
