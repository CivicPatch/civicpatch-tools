import pytest

from core.roster_comparison_report import report_markdown
from schemas.roster_comparisons import (
    ComparedField,
    ComparisonRates,
    FieldCounts,
    JurisdictionRates,
    OutcomeCounts,
    RosterComparisonRun,
    RosterComparisonSummary,
    RunOrganization,
)

_BARRE = "ocd-jurisdiction/country:us/state:vt/place:barre/government"
_GRANBY = "ocd-jurisdiction/country:us/state:vt/place:granby/government"
_PAGE = "https://civicpatch.test/roster-comparisons/run-1"


def _summary(rates: ComparisonRates, corrections: list[str]) -> RosterComparisonSummary:
    barre = ComparisonRates(outcomes=OutcomeCounts(matched=8, only_in_civicpatch=2))
    granby = ComparisonRates(outcomes=OutcomeCounts(only_in_uploaded_data=6))
    return RosterComparisonSummary(
        run=RosterComparisonRun(
            id="run-1", state="vt", started_by_user_id="u", started_at="2026-10-29T00:00:00+00:00",
            source_columns={}, corrections=corrections, rates=rates, jurisdictions_not_named=268,
        ),
        page_url=_PAGE,
        jurisdictions=[
            JurisdictionRates(jurisdiction_ocdid=_GRANBY, rates=granby),
            JurisdictionRates(jurisdiction_ocdid=_BARRE, rates=barre),
        ],
        organizations=[RunOrganization(name="Selectboard", jurisdictions=1, matched=8, civicpatch_people=10)],
        compared_organizations=["Selectboard"],
    )


_RATES = ComparisonRates(
    outcomes=OutcomeCounts(
        matched=8, possible_match=1, only_in_uploaded_data=6, only_in_civicpatch=2, only_in_civicpatch_not_compared=5
    ),
    fields={
        ComparedField.EMAILS: FieldCounts(agreement=6, conflict=1, uploaded_data_has_it=8),
        ComparedField.PHONES: FieldCounts(agreement=5, conflict=2, uploaded_data_has_it=7),
    },
    people_with_conflicts=2,
    rows_with_warnings=1,
)


@pytest.mark.unit
def test_the_report_counts_rows_and_jurisdictions_from_the_saved_counts():
    report = report_markdown(_summary(_RATES, ["row 4: Barre matched by search"]), {_GRANBY: "Granby"})

    assert "## VT roster comparison" in report
    assert "**2 jurisdictions** compared, from 15 rows. 268 jurisdictions of the state" in report
    assert "Organizations compared: Selectboard." in report
    assert "| Possible match, to review | 1 |" in report
    assert "Not counted: 5 of civicpatch's people in organizations not compared." in report
    assert report.rstrip().endswith(f"[Open the comparison]({_PAGE})")


@pytest.mark.unit
def test_the_report_keeps_people_with_conflicts_apart_from_the_field_counts():
    report = report_markdown(_summary(_RATES, []), {})

    assert "| Emails | 75% | 13% |" in report
    assert "| Phones | 63% | 25% |" in report
    assert "Your data had none of: Role, Links, Start date." in report
    assert "2 matched people (25%) conflict in at least one field. A person can conflict in more than one field." in report


@pytest.mark.unit
def test_worth_a_look_names_where_civicpatch_has_no_one_and_counts_warnings_and_corrections():
    report = report_markdown(_summary(_RATES, ["a", "b"]), {_GRANBY: "Granby"})

    assert "- 1 row has warnings" in report
    assert "- civicpatch has no one yet in 1 jurisdiction: Granby." in report
    assert "- The agent's corrections: 2 (listed on the page)." in report


@pytest.mark.unit
def test_a_long_list_of_organizations_is_cut_short_for_the_page():
    many = [f"Board {letter}" for letter in "ABCDEFGHIJ"]
    summary = _summary(_RATES, []).model_copy(update={"compared_organizations": many})

    assert (
        "Organizations compared: Board A, Board B, Board C, Board D, Board E, Board F, Board G, Board H "
        "and 2 more, listed on the page."
        in report_markdown(summary, {})
    )


@pytest.mark.unit
def test_with_nothing_worth_a_look_the_section_is_left_out():
    quiet = _RATES.model_copy(update={"rows_with_warnings": 0})
    summary = _summary(quiet, [])
    summary = summary.model_copy(update={"jurisdictions": summary.jurisdictions[1:]})

    assert "Worth a look" not in report_markdown(summary, {})
