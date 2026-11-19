"""Where a scrape read each person from, as links a reviewer can open.

The source url is the page; the markdown is what the pipeline cached from it, which is the
only way to see what the extractor actually read. Presigned, because the debug bucket is not
public.
"""

import os
from typing import Optional

import database.source_pages as source_pages_db
import lib.buckets as buckets
import lib.storage as storage_service
import shared.utils.id_utils
import shared.utils.url_utils
from core.source_page_outcomes import ScrapePage, ScrapePageRow, scrape_page
from core.source_pages import CachedPage
from schemas.review_cards import ReviewSource


# The two files the pipeline caches per fetched page: what it downloaded, and what it read.
FETCHED_HTML = "original.html"
READ_MARKDOWN = "preprocessed.md"


def _cached_url(
    pipeline_run_id: str, jurisdiction_folder: str, source_url: str, file_name: str
) -> Optional[str]:
    # The debug bucket is keyed by the run that uploaded it, not the changeset it minted.
    relative_path = os.path.join(
        pipeline_run_id,
        "data_source",
        jurisdiction_folder,
        "cache",
        shared.utils.url_utils.format_url_to_folder(source_url),
        file_name,
    )
    return storage_service.get_presigned_url_cached(buckets.DEBUG, relative_path)


def cached_pages_for(
    cached_pages: list[CachedPage], jurisdiction_ocdid: str, pipeline_run_id: Optional[str]
) -> dict[str, CachedPage]:
    """Per canonical url, the page a card may open: its own run's, else the latest published
    one. A changeset with no run (a sheet import) links none."""
    if pipeline_run_id is None:
        return {}
    chosen = _latest_published(cached_pages, jurisdiction_ocdid)
    for cached_page in cached_pages:
        if (
            cached_page.jurisdiction_ocdid == jurisdiction_ocdid
            and cached_page.pipeline_run_id == pipeline_run_id
        ):
            chosen[shared.utils.url_utils.canonical_url(cached_page.source_url)] = cached_page
    return chosen


def _latest_published(
    cached_pages: list[CachedPage], jurisdiction_ocdid: str
) -> dict[str, CachedPage]:
    chosen: dict[str, CachedPage] = {}
    for cached_page in cached_pages:
        if not (cached_page.is_published and cached_page.jurisdiction_ocdid == jurisdiction_ocdid):
            continue
        key = shared.utils.url_utils.canonical_url(cached_page.source_url)
        if key not in chosen or cached_page.cached_at > chosen[key].cached_at:
            chosen[key] = cached_page
    return chosen


async def sources_for_card(
    jurisdiction_ocdid: str, pipeline_run_id: Optional[str], source_urls: list[str]
) -> list[ReviewSource]:
    """The read behind a card's links, shared by both routers."""
    if not source_urls:
        return []
    cached_pages = await source_pages_db.get_cached_pages(
        [jurisdiction_ocdid], [pipeline_run_id] if pipeline_run_id else []
    )
    return build_sources(
        cached_pages_for(cached_pages, jurisdiction_ocdid, pipeline_run_id),
        source_urls,
        pipeline_run_id,
    )


def _cached_page_url(cached_page: Optional[CachedPage], file_name: str) -> Optional[str]:
    if cached_page is None:
        return None
    return storage_service.get_presigned_url_cached(
        buckets.DEBUG, os.path.join(cached_page.cache_path, file_name)
    )


def build_sources(
    cached_pages: dict[str, CachedPage],
    source_urls: list[str],
    pipeline_run_id: Optional[str],
) -> list[ReviewSource]:
    """The page for everyone, with the cached page when there is one."""
    return [
        _source_of(
            cached_pages.get(shared.utils.url_utils.canonical_url(url)), url, pipeline_run_id
        )
        for url in source_urls
    ]


def _source_of(
    cached_page: Optional[CachedPage], url: str, pipeline_run_id: Optional[str]
) -> ReviewSource:
    return ReviewSource(
        url=url,
        markdown=_cached_page_url(cached_page, READ_MARKDOWN),
        html=_cached_page_url(cached_page, FETCHED_HTML),
        cached_at=cached_page.cached_at if cached_page else None,
        is_cached_by_this_scrape=(
            cached_page is not None and cached_page.pipeline_run_id == pipeline_run_id
        ),
    )


def without_debug_links(sources: list[ReviewSource]) -> list[ReviewSource]:
    """What a non-admin gets: which pages a person came from, not the debug bucket's copies."""
    return [
        source.model_copy(update={"markdown": None, "html": None}) for source in sources
    ]


def scrape_page_with_cached_copies(row: ScrapePageRow) -> ScrapePage:
    """The admin's view of a page a scrape read: also links to what the pipeline cached of it."""
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(row.jurisdiction_ocdid)
    return scrape_page(row).model_copy(
        update={
            "markdown_url": _cached_url(row.pipeline_run_id, folder, row.source_url, READ_MARKDOWN),
            "html_url": _cached_url(row.pipeline_run_id, folder, row.source_url, FETCHED_HTML),
        }
    )
