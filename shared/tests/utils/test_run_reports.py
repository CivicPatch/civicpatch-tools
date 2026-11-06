"""The questions cp.org asks of a governing-law run's report: did it store anything, or meet a block."""

import pytest

from shared.schemas import FoundBy
from shared.utils.run_reports import GoverningLawReport, GoverningLawSearch, TriedReason, TriedUrl

pytestmark = pytest.mark.unit

_SITE = "http://www.malheurco.org"


def _report(tried: list[TriedUrl]) -> GoverningLawReport:
    search = GoverningLawSearch(found_by=FoundBy.SEARCH, classification="county", tried=tried)
    return GoverningLawReport(answer=search)


def test_a_refusal_challenge_or_robots_rule_is_a_block_and_a_crawled_site_is_not():
    for reason in (TriedReason.REFUSED, TriedReason.CHALLENGED, TriedReason.DISALLOWED_BY_ROBOTS):
        assert _report([TriedUrl(url=_SITE, reason=reason)]).blocked
    assert not _report([TriedUrl(url=_SITE, reason=TriedReason.SITE_CRAWLED)]).blocked


def test_a_run_with_no_answer_met_no_block_and_stored_nothing():
    report = GoverningLawReport()

    assert not report.blocked
    assert not report.stored_anything
