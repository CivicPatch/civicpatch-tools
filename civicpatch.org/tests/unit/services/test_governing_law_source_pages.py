"""A governing-law page against patched `lib.storage` and `database`: what is written where,
and what a missing one becomes."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

import lib.buckets as buckets
from database.governing_law import GoverningLawRow
from services.governing_law_source_pages import (
    NotPlainText,
    SourcePageNotFound,
    UnknownJurisdiction,
    read_source_page,
    store_source_page,
)
from shared.schemas import GoverningLawSourcePage

pytestmark = pytest.mark.unit

MODULE = "services.governing_law_source_pages"
_OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_URL = "https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX/149"
_TEXT = "# Chapter 149\n\n§ 1. Corporate existence retained.\n"
_ROW = GoverningLawRow(jurisdiction_ocdid=_OCDID, name="Stowe town", governing_law=None)
_PAGE = GoverningLawSourcePage(
    id="row-1", jurisdiction_ocdid=_OCDID, source_url=_URL, page_hash="abc", cache_path="governing_law/abc.md",
    collected_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
)


def _known(row=_ROW):
    return patch(f"{MODULE}.governing_law_db.get_governing_law_row", new=AsyncMock(return_value=row))


@pytest.mark.asyncio
async def test_the_text_goes_to_artifacts_under_its_hash_and_the_row_points_at_it():
    with _known(), patch("lib.storage.upload_bytes_to_storage") as upload, patch(
        f"{MODULE}.source_pages_db.insert_governing_law_source_page", new=AsyncMock(return_value=_PAGE)
    ) as insert:
        page = await store_source_page(_OCDID, _URL, _TEXT)

    bucket, key, body, content_type = upload.call_args.args
    assert bucket == buckets.ARTIFACTS
    assert key.startswith("governing_law/") and key.endswith(".md")
    assert (body, content_type) == (_TEXT.encode(), "text/markdown")
    page_hash = key.removeprefix("governing_law/").removesuffix(".md")
    insert.assert_awaited_once_with(_OCDID, _URL, page_hash, key)
    assert page == _PAGE


@pytest.mark.asyncio
async def test_html_and_an_unknown_jurisdiction_are_refused_before_anything_is_written():
    with _known(), patch("lib.storage.upload_bytes_to_storage") as upload, pytest.raises(NotPlainText):
        await store_source_page(_OCDID, _URL, "<html><body>§ 1.</body></html>")
    with _known(None), patch("lib.storage.upload_bytes_to_storage") as upload_unknown, pytest.raises(UnknownJurisdiction):
        await store_source_page(_OCDID, _URL, _TEXT)
    upload.assert_not_called()
    upload_unknown.assert_not_called()


@pytest.mark.asyncio
async def test_a_page_is_read_back_from_artifacts():
    with patch(f"{MODULE}.source_pages_db.get_governing_law_source_page", new=AsyncMock(return_value=_PAGE)), patch(
        "lib.storage.download_bytes_from_storage", return_value=_TEXT.encode()
    ) as download:
        found = await read_source_page(_OCDID, "row-1")

    assert download.call_args.args == (buckets.ARTIFACTS, "governing_law/abc.md")
    assert (found.page, found.text) == (_PAGE, _TEXT)


@pytest.mark.asyncio
async def test_a_row_that_is_not_the_jurisdictions_or_has_no_object_is_not_found():
    with patch(f"{MODULE}.source_pages_db.get_governing_law_source_page", new=AsyncMock(return_value=None)), pytest.raises(
        SourcePageNotFound
    ):
        await read_source_page(_OCDID, "row-9")
    with patch(f"{MODULE}.source_pages_db.get_governing_law_source_page", new=AsyncMock(return_value=_PAGE)), patch(
        "lib.storage.download_bytes_from_storage", return_value=None
    ), pytest.raises(SourcePageNotFound):
        await read_source_page(_OCDID, "row-1")
