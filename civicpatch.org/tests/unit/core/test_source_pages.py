"""A run's frontier as `source_pages` rows."""

import pytest

from core.source_pages import (
    LINK_STATUS_HEURISTICS_FAIL,
    FrontierLink,
    frontier_links,
    source_page_rows,
)

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:wa/place:ellensburg/government"
_RUN = "run-1"
_COUNCIL_ORG = "00000000-0000-4000-8000-0000000000c1"


def _link(**fields) -> FrontierLink:
    return FrontierLink(**{"url": "https://ci.ellensburg.wa.us/", "status": "done", **fields})


def _rows(*links: FrontierLink, changeset_id: str | None = "changeset-1"):
    return source_page_rows(list(links), _RUN, _OCDID, changeset_id)


def test_a_page_never_fetched_gets_no_row():
    assert _rows(_link(status="pending")) == []


def test_a_page_that_failed_to_load_still_gets_a_row_with_nothing_to_say():
    [row] = _rows(_link(status="error"))

    assert (row.page_hash, row.is_relevant, row.cache_path) == (None, None, None)


def test_the_cache_path_is_where_cp_org_uploaded_the_page_folder():
    [row] = _rows(_link(folder_name="ci_ellensburg_wa_us_100_city-council"))

    assert row.cache_path == (
        "run-1/data_source/wa/local/place_ellensburg/cache/ci_ellensburg_wa_us_100_city-council"
    )


def test_a_page_that_failed_extraction_is_a_read_of_nobody():
    """Its coverage answer stays on the link; the row must not retire that organization."""
    [row] = _rows(_link(status=LINK_STATUS_HEURISTICS_FAIL, organization_ids=[_COUNCIL_ORG]))

    assert row.organization_ids == []


def test_a_relevant_page_carries_its_organizations_and_verdict():
    link = _link(
        organization_ids=[_COUNCIL_ORG],
        is_relevant=True,
        relevant_urls=["https://ci.ellensburg.wa.us/975/Meet-Your-City-Council"],
        page_hash="p",
        prompt_hash="q",
        text="City Council",
    )

    [row] = _rows(link)

    assert row.organization_ids == [_COUNCIL_ORG]
    assert (row.is_relevant, row.page_hash, row.prompt_hash, row.anchor_text) == (
        True,
        "p",
        "q",
        "City Council",
    )


def test_a_reused_page_points_at_the_row_the_llm_read():
    [row] = _rows(_link(unchanged_since_source_page_id="row-0"))

    assert row.unchanged_since_source_page_id == "row-0"


def test_a_failed_run_writes_its_pages_with_no_changeset():
    [row] = _rows(_link(), changeset_id=None)

    assert row.changeset_id is None


def test_a_run_that_wrote_no_context_has_no_links():
    assert frontier_links({}) == []


def test_links_are_read_from_the_saved_context():
    context = {"data": {"frontier": {"links": {"k": {"url": "https://x.gov/", "status": "done"}}}}}

    assert frontier_links(context) == [FrontierLink(url="https://x.gov/", status="done")]
