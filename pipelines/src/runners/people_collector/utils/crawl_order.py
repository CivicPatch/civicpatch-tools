"""Which queued page to crawl next. Pure: urls in, a url out."""

from collections import Counter

from shared.utils.url_utils import get_path


def url_section(url: str) -> str:
    """The first path segment — `/council/members/x` is `council`, the homepage is `""`."""
    return get_path(url).strip("/").split("/")[0].lower()


def least_crawled_section_first(queue: list[str], crawled: list[str]) -> str | None:
    """The first url in `queue` whose site section has been crawled least.

    `queue` arrives ranked, so ranking still decides between equally crawled sections and within
    one. Taking sections in turn — Mercator's per-host queues, a section standing in for an organization —
    stops one organization's navigation, repeated on every page of it, from starving another organization.
    """
    crawled_per_section = Counter(url_section(url) for url in crawled)
    chosen = None
    for url in queue:
        if chosen is None or crawled_per_section[url_section(url)] < crawled_per_section[url_section(chosen)]:
            chosen = url
    return chosen
