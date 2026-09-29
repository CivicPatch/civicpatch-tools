"""Where a scrape read each person from, as links a reviewer can open.

The source url is the page; the markdown is what the pipeline cached from it, which is the
only way to see what the extractor actually read. Presigned, because the debug bucket is not
public.
"""

import os
from typing import Optional

import lib.buckets as buckets
import lib.storage as storage_service
import shared.utils.id_utils
import shared.utils.url_utils


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


def build_sources(
    pipeline_run_id: str | None, jurisdiction_ocdid: str, source_urls: list[str]
) -> list[dict]:
    """A changeset with no run (a sheet import) has pages but no cached copies of them."""
    if pipeline_run_id is None:
        return [{"url": url, "markdown": None, "html": None} for url in source_urls]
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return [
        {
            "url": url,
            "markdown": _cached_url(pipeline_run_id, folder, url, READ_MARKDOWN),
            "html": _cached_url(pipeline_run_id, folder, url, FETCHED_HTML),
        }
        for url in source_urls
    ]


def without_debug_links(sources: list[dict]) -> list[dict]:
    """What a non-admin gets: which pages a person came from, not the debug bucket's copies."""
    return [{**source, "markdown": None, "html": None} for source in sources]
