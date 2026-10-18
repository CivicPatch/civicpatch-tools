"""A governing-law page: its text in the artifacts bucket, its row in
`governing_law_source_pages`, both reached only through here so the pipeline never holds
bucket credentials."""

import asyncio

import database.governing_law as governing_law_db
import database.governing_law_source_pages as source_pages_db
import lib.buckets as buckets
import lib.storage as storage
from core import governing_law_source_pages
from pydantic import BaseModel
from shared.schemas import GoverningLawSourcePage


class GoverningLawSourcePageText(BaseModel):
    page: GoverningLawSourcePage
    text: str


class UnknownJurisdiction(Exception):
    pass


class NotPlainText(Exception):
    pass


class SourcePageNotFound(Exception):
    pass


async def store_source_page(jurisdiction_ocdid: str, source_url: str, text: str) -> GoverningLawSourcePage:
    """Refuses a page that still carries HTML: the cache holds text, never the page."""
    if await governing_law_db.get_governing_law_row(jurisdiction_ocdid) is None:
        raise UnknownJurisdiction(jurisdiction_ocdid)
    if governing_law_source_pages.carries_html(text):
        raise NotPlainText()
    page_hash = governing_law_source_pages.page_hash(text)
    cache_path = governing_law_source_pages.cache_path(page_hash)
    # boto3 is synchronous and would block the event loop, as in `sinks.parquet`.
    await asyncio.to_thread(
        storage.upload_bytes_to_storage,
        buckets.ARTIFACTS,
        cache_path,
        text.encode(),
        governing_law_source_pages.CONTENT_TYPE,
    )
    return await source_pages_db.insert_governing_law_source_page(jurisdiction_ocdid, source_url, page_hash, cache_path)


async def read_source_page(jurisdiction_ocdid: str, source_page_id: str) -> GoverningLawSourcePageText:
    page = await source_pages_db.get_governing_law_source_page(jurisdiction_ocdid, source_page_id)
    if page is None:
        raise SourcePageNotFound(source_page_id)
    body = await asyncio.to_thread(storage.download_bytes_from_storage, buckets.ARTIFACTS, page.cache_path)
    if body is None:
        raise SourcePageNotFound(source_page_id)
    return GoverningLawSourcePageText(page=page, text=body.decode())
