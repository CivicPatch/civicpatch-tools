"""Turning a url into raw bytes. A plain GET first; the browser only when the plain page turned
out thin. A host that refuses (403, 429) is never retried another way: that is a refusal, and the
publisher rules say stop."""

from runners.governing_law_collector.fetchers import browser, plain
from runners.governing_law_collector.fetchers.plain import RefusedByHost
from runners.governing_law_collector.schemas import FetchedPage

__all__ = ["RefusedByHost", "fetch"]


async def fetch(url: str, by_browser: bool) -> FetchedPage:
    if by_browser:
        return await browser.fetch(url)
    return await plain.fetch(url)
