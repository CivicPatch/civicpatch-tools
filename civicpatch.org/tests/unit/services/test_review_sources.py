"""Which cached page a card links, and what the link points at: the choice, the key, the sheet import."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from core.source_pages import CachedPage
from schemas.review_cards import ReviewSource
from services.review_sources import (
    build_sources,
    cached_pages_for,
    sources_for_card,
    without_debug_links,
)
from shared.utils.url_utils import canonical_url

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
_OTHER_OCDID = "ocd-jurisdiction/country:us/state:wa/place:tacoma/government"
_URL = "https://seattle.gov/council"
_RUN = "run-1"
_PUBLISHED_RUN = "run-0"
_CACHED_AT = datetime(2026, 11, 19, tzinfo=timezone.utc)


def _cached_page(
    run_id: str = _RUN,
    url: str = _URL,
    is_published: bool = False,
    cached_at: datetime = _CACHED_AT,
    jurisdiction_ocdid: str = _OCDID,
) -> CachedPage:
    return CachedPage(
        jurisdiction_ocdid=jurisdiction_ocdid,
        source_url=url,
        pipeline_run_id=run_id,
        cache_path=f"{run_id}/data_source/wa/local/place_seattle/cache/council",
        cached_at=cached_at,
        is_published=is_published,
    )


def _presigned_verbatim(bucket: str, key: str) -> str:
    return key


def test_the_cards_own_runs_cached_page_wins_over_a_later_published_one():
    own = _cached_page(cached_at=_CACHED_AT - timedelta(days=30))
    published = _cached_page(_PUBLISHED_RUN, is_published=True)

    assert cached_pages_for([own, published], _OCDID, _RUN) == {canonical_url(_URL): own}


def test_the_latest_published_cached_page_is_the_fallback():
    older = _cached_page("run-a", is_published=True, cached_at=_CACHED_AT - timedelta(days=1))
    newer = _cached_page("run-b", is_published=True)

    assert list(cached_pages_for([older, newer], _OCDID, _RUN).values()) == [newer]


def test_another_cards_open_run_is_never_the_fallback():
    """A batch passes every card's run, so another card's unpublished page shows up here."""
    assert cached_pages_for([_cached_page("run-other")], _OCDID, _RUN) == {}


def test_urls_that_differ_only_in_canonical_form_are_one_page():
    published = _cached_page(_PUBLISHED_RUN, is_published=True, url=f"http://www.seattle.gov/council/#top")

    chosen = cached_pages_for([published], _OCDID, _RUN)

    assert chosen[canonical_url(_URL)] is published


def test_a_url_read_in_two_jurisdictions_is_two_cached_pages():
    seattle = _cached_page(_PUBLISHED_RUN, is_published=True)
    tacoma = _cached_page("run-2", is_published=True, jurisdiction_ocdid=_OTHER_OCDID)

    assert list(cached_pages_for([seattle, tacoma], _OCDID, _RUN).values()) == [seattle]


def test_a_changeset_with_no_run_links_no_cached_page():
    assert cached_pages_for([_cached_page(_PUBLISHED_RUN, is_published=True)], _OCDID, None) == {}


def test_the_link_is_the_stored_cache_path_not_a_folder_guessed_from_the_url():
    cached_page = _cached_page(is_published=True)

    with patch(
        "services.review_sources.storage_service.get_presigned_url_cached",
        side_effect=_presigned_verbatim,
    ):
        [source] = build_sources(
            cached_pages_for([cached_page], _OCDID, _RUN), [_URL], _RUN
        )

    assert source.markdown == f"{cached_page.cache_path}/preprocessed.md"
    assert source.html == f"{cached_page.cache_path}/original.html"


def test_a_page_with_no_cached_copy_keeps_its_url_and_has_no_links():
    [source] = build_sources({}, [_URL], _RUN)

    assert (source.url, source.markdown, source.html) == (_URL, None, None)
    assert (source.cached_at, source.is_cached_by_this_scrape) == (None, False)


def test_a_cards_own_runs_cached_page_says_this_scrape_read_it():
    [source] = build_sources(cached_pages_for([_cached_page()], _OCDID, _RUN), [_URL], _RUN)

    assert (source.cached_at, source.is_cached_by_this_scrape) == (_CACHED_AT, True)


def test_an_earlier_published_page_says_the_copy_is_not_this_scrapes():
    published = _cached_page(
        _PUBLISHED_RUN, is_published=True, cached_at=_CACHED_AT - timedelta(days=30)
    )

    [source] = build_sources(
        cached_pages_for([published], _OCDID, _RUN), [_URL], _RUN
    )

    assert (source.cached_at, source.is_cached_by_this_scrape) == (
        _CACHED_AT - timedelta(days=30),
        False,
    )


@pytest.mark.asyncio
async def test_a_sheet_import_card_links_no_published_cached_page():
    with patch(
        "services.review_sources.source_pages_db.get_cached_pages",
        return_value=[_cached_page(_PUBLISHED_RUN, is_published=True)],
    ):
        [source] = await sources_for_card(_OCDID, None, [_URL])

    assert (source.url, source.markdown, source.html) == (_URL, None, None)
    assert (source.cached_at, source.is_cached_by_this_scrape) == (None, False)


def test_a_non_admin_keeps_the_page_and_its_date_but_not_the_debug_links():
    source = ReviewSource(
        url=_URL,
        markdown="m",
        html="h",
        cached_at=_CACHED_AT,
        is_cached_by_this_scrape=False,
    )

    [stripped] = without_debug_links([source])

    assert (stripped.markdown, stripped.html) == (None, None)
    assert (stripped.cached_at, stripped.is_cached_by_this_scrape) == (_CACHED_AT, False)
