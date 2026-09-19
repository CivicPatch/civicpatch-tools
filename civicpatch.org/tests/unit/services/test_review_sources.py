"""Where a person was read from: the page for everyone, the debug bucket's copies for admins."""

from unittest.mock import patch

import pytest

from services.review_sources import build_sources, without_debug_links

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
_URL = "https://seattle.gov/council"


def test_each_source_links_the_fetched_html_and_the_markdown_read_from_it():
    with patch(
        "services.review_sources.storage_service.get_presigned_url_cached",
        side_effect=lambda bucket, key: key,
    ):
        [source] = build_sources("changeset-1", _OCDID, [_URL])

    assert source["url"] == _URL
    assert source["markdown"].startswith("changeset-1/data_source/")
    assert source["markdown"].endswith("/preprocessed.md")
    assert source["html"].endswith("/original.html")


def test_a_non_admin_keeps_the_page_but_not_the_debug_links():
    stripped = without_debug_links([{"url": _URL, "markdown": "m", "html": "h"}])

    assert stripped == [{"url": _URL, "markdown": None, "html": None}]
