"""The issue a collector run files, from the report it sends: pipeline 1's misses by kind of place,
and pipeline 2's runs that read nothing or stopped at the cap."""

import pytest
from shared.schemas import FoundBy
from shared.utils.layered_config import GovernedBy
from shared.utils.run_reports import CostCapDetail, GoverningLawReport, GoverningLawSearch, OrganizationsRunReport, TriedReason, TriedUrl
from shared.utils.statuses import PipelineIssueType, PipelineRunKind

from decimal import Decimal

from core.pipeline_run_issues import ISSUE_READERS, Missing, governing_law_issue, organizations_issue, run_issue

pytestmark = pytest.mark.unit

_COUNTY = GovernedBy.CHARTER_ELSE_GENERAL_LAW
_CITY = GovernedBy.CHARTER
_CRAWLED = [TriedUrl(url="http://www.malheurco.org", reason=TriedReason.SITE_CRAWLED)]
_REFUSED = [TriedUrl(url="https://library.municode.com/or/carlton/codes/code_of_ordinances", reason=TriedReason.REFUSED)]


def _report(
    governed_by: GovernedBy, tried: list[TriedUrl], charter_ids=(), general_law_ids=("statute-row",), found_by=FoundBy.SEARCH
) -> GoverningLawReport:
    return GoverningLawReport(
        answer=GoverningLawSearch(found_by=found_by, classification="place", tried=tried),
        charter_source_page_ids=list(charter_ids),
        general_law_source_page_ids=list(general_law_ids),
        governed_by=governed_by,
    )


def test_a_county_with_no_charter_found_by_a_clean_search_reads_the_general_law_with_no_issue():
    assert governing_law_issue(_report(_COUNTY, _CRAWLED)) is None


def test_a_county_whose_search_was_refused_is_source_blocked():
    issue = governing_law_issue(_report(_COUNTY, _REFUSED))

    assert issue is not None
    assert issue.issue_type == PipelineIssueType.SOURCE_BLOCKED
    assert issue.data == {"missing": Missing.CHARTER, "tried": [entry.model_dump(mode="json") for entry in _REFUSED], "skipped_urls": []}


def test_a_city_where_every_place_has_a_charter_and_none_was_found_is_not_found():
    issue = governing_law_issue(_report(_CITY, _CRAWLED))

    assert issue is not None
    assert issue.issue_type == PipelineIssueType.GOVERNING_LAW_NOT_FOUND
    assert issue.data["missing"] == Missing.CHARTER


def test_a_city_whose_search_was_refused_is_source_blocked():
    issue = governing_law_issue(_report(_CITY, _REFUSED))

    assert issue is not None
    assert issue.issue_type == PipelineIssueType.SOURCE_BLOCKED


def test_a_found_charter_files_nothing():
    assert governing_law_issue(_report(_CITY, _CRAWLED, charter_ids=("charter-row",))) is None


def test_a_state_index_naming_no_charter_is_an_answer():
    assert governing_law_issue(_report(_CITY, [], found_by=FoundBy.STATE_INDEX)) is None


def test_nothing_stored_at_all_is_missing_everything_whatever_the_place():
    issue = governing_law_issue(_report(_COUNTY, _CRAWLED, general_law_ids=()))

    assert issue is not None
    assert issue.data["missing"] == Missing.EVERYTHING
    assert issue.issue_type == PipelineIssueType.GOVERNING_LAW_NOT_FOUND


def test_a_run_that_never_searched_files_nothing():
    assert governing_law_issue(GoverningLawReport()) is None


def test_the_reader_takes_a_pipeline_1_context_with_fields_it_does_not_need():
    data = _report(_COUNTY, _REFUSED).model_dump(mode="json") | {"jurisdiction_ocdid": "ocd-jurisdiction/x", "config": {"name": "Malheur County"}}

    issue = ISSUE_READERS[PipelineRunKind.GOVERNING_LAW_COLLECTOR](data)

    assert issue is not None
    assert issue.issue_type == PipelineIssueType.SOURCE_BLOCKED


@pytest.mark.parametrize(
    "report,expected",
    [
        (OrganizationsRunReport(input_hash=None), PipelineIssueType.NO_GOVERNING_LAW),
        (OrganizationsRunReport(input_hash="7c21", stopped_at_cost_cap=True), PipelineIssueType.COST_CAP_REACHED),
    ],
)
def test_pipeline_2_files_when_it_read_nothing_or_stopped_at_the_cap(report: OrganizationsRunReport, expected: PipelineIssueType):
    issue = organizations_issue(report)

    assert issue is not None
    assert issue.issue_type == expected


def test_a_pipeline_2_run_that_read_and_asked_everything_files_nothing():
    assert organizations_issue(OrganizationsRunReport(input_hash="7c21")) is None


def test_a_capped_pipeline_2_run_says_which_roles_went_unasked_and_what_it_spent():
    cost_cap = CostCapDetail(spent_usd=Decimal("0.05"), cap_usd=Decimal("0.05"), unfinished=["clerk", "treasurer"])
    report = OrganizationsRunReport(input_hash="7c21", stopped_at_cost_cap=True, cost_cap=cost_cap)

    issue = organizations_issue(report)

    assert issue is not None
    assert issue.data == {"spent_usd": "0.05", "cap_usd": "0.05", "unfinished": ["clerk", "treasurer"]}


def test_a_run_that_ended_in_error_files_pipeline_error_with_its_failure_whatever_its_kind():
    context = {
        "current_state": "ERROR",
        "failure": {"failed_state": "FIND_SOURCES", "error": "TimeoutError: crawl"},
        "data": _report(_CITY, _CRAWLED).model_dump(mode="json"),
    }

    issue = run_issue(PipelineRunKind.GOVERNING_LAW_COLLECTOR, context)

    assert issue is not None
    assert issue.issue_type == PipelineIssueType.PIPELINE_ERROR
    assert issue.data == {"error": "TimeoutError: crawl", "failed_state": "FIND_SOURCES"}


def test_a_run_that_ended_well_files_what_its_kind_reads():
    context = {"current_state": "SUCCESS", "data": {"input_hash": None}}

    issue = run_issue(PipelineRunKind.ORGANIZATIONS_COLLECTOR, context)

    assert issue is not None
    assert issue.issue_type == PipelineIssueType.NO_GOVERNING_LAW
