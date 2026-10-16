from datetime import datetime, timezone

import pytest

from core.source_page_outcomes import PageOutcome, ScrapePageRow, page_outcome

pytestmark = pytest.mark.unit


def _row(**changes) -> ScrapePageRow:
    read = ScrapePageRow(
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:ellensburg/government",
        pipeline_run_id="run",
        source_url="https://ci.ellensburg.wa.us/100/City-Council",
        page_hash="abc",
        is_relevant=True,
        heuristics_failures=[],
        unchanged_since=None,
        organization_names=["City Council"],
        people_count=7,
    )
    return read.model_copy(update=changes)


def test_a_page_that_listed_people_was_read():
    assert page_outcome(_row()) == PageOutcome.READ


def test_a_page_reused_from_an_earlier_reading_is_unchanged():
    assert page_outcome(_row(unchanged_since=datetime(2026, 7, 12, tzinfo=timezone.utc))) == PageOutcome.UNCHANGED


def test_a_page_with_no_hash_failed_to_load():
    assert page_outcome(_row(page_hash=None, is_relevant=None, people_count=0)) == PageOutcome.FAILED_TO_LOAD


def test_a_page_judged_irrelevant_is_not_about_officials():
    assert page_outcome(_row(is_relevant=False, people_count=0)) == PageOutcome.NOT_ABOUT_OFFICIALS


def test_a_relevant_page_whose_extraction_failed_and_listed_nobody():
    assert page_outcome(_row(heuristics_failures=["name"], people_count=0)) == PageOutcome.EXTRACTION_FAILED


def test_a_failed_check_on_one_person_still_counts_as_read():
    assert page_outcome(_row(heuristics_failures=["phone"], people_count=6)) == PageOutcome.READ
