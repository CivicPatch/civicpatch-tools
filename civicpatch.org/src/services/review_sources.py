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


def _cached_markdown_url(
    changeset_id: str, jurisdiction_folder: str, source_url: str
) -> Optional[str]:
    relative_path = os.path.join(
        changeset_id,
        "data_source",
        jurisdiction_folder,
        "cache",
        shared.utils.url_utils.format_url_to_folder(source_url),
        "preprocessed.md",
    )
    return storage_service.get_presigned_url_cached(buckets.DEBUG, relative_path)


def build_sources(
    changeset_id: str, jurisdiction_ocdid: str, source_urls: list[str]
) -> list[dict]:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return [
        {"url": url, "markdown": _cached_markdown_url(changeset_id, folder, url)}
        for url in source_urls
    ]
