"""The questions cp.org asks of a governing-law run's report: did it store, search, or meet a block."""

import pytest

from shared.schemas import FoundBy
from shared.utils.run_reports import GoverningLawReport, GoverningLawSearch, TriedReason, TriedUrl

pytestmark = pytest.mark.unit

_SITE = "http://www.malheurco.org"


def _report(tried: list[TriedUrl], stored: list[str] = [], skipped: list[str] = []) -> GoverningLawReport:
    search = GoverningLawSearch(found_by=FoundBy.SEARCH, classification="county", tried=tried)
    return GoverningLawReport(answer=search, general_law_source_page_ids=stored, skipped_urls=skipped)


def test_a_refusal_challenge_or_robots_rule_is_a_block_and_a_crawled_site_is_not():
    for reason in (TriedReason.REFUSED, TriedReason.CHALLENGED, TriedReason.DISALLOWED_BY_ROBOTS):
        assert _report([TriedUrl(url=_SITE, reason=reason)]).blocked
    assert not _report([TriedUrl(url=_SITE, reason=TriedReason.SITE_CRAWLED)]).blocked


def test_a_run_that_tried_skipped_or_stored_anything_searched():
    assert _report([TriedUrl(url=_SITE, reason=TriedReason.SITE_CRAWLED)]).searched_anything
    assert _report([], skipped=[_SITE]).searched_anything
    assert _report([], stored=["statute-row"]).searched_anything
    assert not _report([]).searched_anything


def test_a_run_with_no_answer_searched_nothing_and_met_no_block():
    report = GoverningLawReport()

    assert not report.searched_anything
    assert not report.blocked
    assert not report.stored_anything
