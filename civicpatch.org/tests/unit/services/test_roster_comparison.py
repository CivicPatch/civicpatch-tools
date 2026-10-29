"""The service's reads of a saved run. The database is the boundary mocked; the queries themselves
are tested in tests/integration/database/test_roster_comparisons.py."""

from unittest.mock import AsyncMock, patch

import pytest

import services.roster_comparison as service
from schemas.roster_comparisons import (
    ComparedField,
    ComparisonRates,
    FieldFilter,
    FieldLevel,
    JurisdictionRates,
    OutcomeCounts,
    PeopleFilter,
    PersonOutcome,
    RejectedReason,
    RejectedRow,
    RosterComparisonRun,
    RunOrganization,
)

_RUN_ID = "11111111-1111-1111-1111-111111111111"
_BARRE = "ocd-jurisdiction/country:us/state:vt/place:barre/government"
_STOWE = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"


def _run() -> RosterComparisonRun:
    return RosterComparisonRun(
        id=_RUN_ID, state="vt", started_by_user_id="u", started_at="2026-10-22T00:00:00+00:00",
        source_columns={}, corrections=[], rates=ComparisonRates(), jurisdictions_not_named=0,
    )


def _database(name: str, **kwargs):
    return patch.object(service.database, name, new=AsyncMock(**kwargs))


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_summary_lists_jurisdictions_most_unmatched_first_with_the_runs_page():
    jurisdictions = [
        JurisdictionRates(jurisdiction_ocdid=_STOWE, rates=ComparisonRates()),
        JurisdictionRates(jurisdiction_ocdid=_BARRE, rates=ComparisonRates(outcomes=OutcomeCounts(only_in_civicpatch=2))),
    ]
    with _database("get_roster_comparison_run", return_value=_run()), _database(
        "get_roster_comparison_jurisdictions", return_value=jurisdictions
    ), _database("get_roster_comparison_organizations", return_value=[]), _database(
        "count_roster_comparison_not_compared", return_value={}
    ), patch.object(
        service.environment, "instance_url", return_value="https://civicpatch.test"
    ):
        summary = await service.get_run_summary(_RUN_ID, None)

    assert [j.jurisdiction_ocdid for j in summary.jurisdictions] == [_BARRE, _STOWE]
    assert summary.page_url == f"https://civicpatch.test/roster-comparisons/{_RUN_ID}"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_field_page_queries_the_filters_levels_and_reports_the_house_paging():
    people_filter = PeopleFilter(field=ComparedField.EMAILS, level=FieldFilter.CONFLICT)
    with _database("get_roster_comparison_run", return_value=_run()), _database(
        "get_roster_comparison_people_page", return_value=(120, [])
    ) as people, _database("get_roster_comparison_organizations", return_value=[]):
        page = await service.get_run_people_page(_RUN_ID, people_filter, ["Selectboard"], 2, 50)

    assert (page.total_items, page.page, page.total_pages) == (120, 2, 3)
    people.assert_awaited_once_with(
        _RUN_ID, None, ComparedField.EMAILS, [FieldLevel.DIFFERS], ["Selectboard"], 50, 50
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_an_outcome_page_queries_no_field_levels():
    people_filter = PeopleFilter(outcome=PersonOutcome.ONLY_IN_UPLOADED_DATA)
    with _database("get_roster_comparison_run", return_value=_run()), _database(
        "get_roster_comparison_people_page", return_value=(0, [])
    ) as people, _database("get_roster_comparison_organizations", return_value=[]):
        await service.get_run_people_page(_RUN_ID, people_filter, ["Selectboard"], 1, 50)

    people.assert_awaited_once_with(_RUN_ID, PersonOutcome.ONLY_IN_UPLOADED_DATA, None, [], ["Selectboard"], 50, 0)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reading_an_unknown_run_raises_run_not_found():
    with _database("get_roster_comparison_run", return_value=None):
        with pytest.raises(service.RunNotFound, match="No roster comparison"):
            await service.get_run_people(_RUN_ID, _BARRE, None)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_created_run_reports_the_rates_the_page_shows_by_default():
    run = _run().model_copy(update={"rates": ComparisonRates(outcomes=OutcomeCounts(matched=2, only_in_civicpatch=6))})
    with _database("get_roster_comparison_run", return_value=run), _database(
        "get_roster_comparison_jurisdictions", return_value=[]
    ), _database(
        "get_roster_comparison_organizations", return_value=[_organization("Selectboard", 2)]
    ), _database("count_roster_comparison_not_compared", return_value={_BARRE: 4}), patch.object(
        service.environment, "instance_url", return_value="https://civicpatch.test"
    ):
        created = await service.get_run_created(_RUN_ID)

    outcomes = created.rates.outcomes
    assert (outcomes.only_in_civicpatch, outcomes.only_in_civicpatch_not_compared) == (2, 4)
    assert created.page_url == f"https://civicpatch.test/roster-comparisons/{_RUN_ID}"


def _organization(name: str, matched: int) -> RunOrganization:
    return RunOrganization(name=name, jurisdictions=1, matched=matched, civicpatch_people=matched + 3)


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    ("asked", "compared"),
    [(None, ["Selectboard"]), (["Selectboard", "Board of Listers"], ["Selectboard", "Board of Listers"])],
)
async def test_a_summary_moves_the_not_compared_out_of_only_in_civicpatch(asked, compared):
    jurisdictions = [
        JurisdictionRates(jurisdiction_ocdid=_BARRE, rates=ComparisonRates(outcomes=OutcomeCounts(only_in_civicpatch=5))),
        JurisdictionRates(jurisdiction_ocdid=_STOWE, rates=ComparisonRates(outcomes=OutcomeCounts(only_in_civicpatch=1))),
    ]
    run = _run().model_copy(update={"rates": ComparisonRates(outcomes=OutcomeCounts(matched=2, only_in_civicpatch=6))})
    organizations = [_organization("Selectboard", 2), _organization("Board of Listers", 0)]
    with _database("get_roster_comparison_run", return_value=run), _database(
        "get_roster_comparison_jurisdictions", return_value=jurisdictions
    ), _database("get_roster_comparison_organizations", return_value=organizations), _database(
        "count_roster_comparison_not_compared", return_value={_BARRE: 4}
    ) as count, patch.object(service.environment, "instance_url", return_value="https://civicpatch.test"):
        summary = await service.get_run_summary(_RUN_ID, asked)

    count.assert_awaited_once_with(_RUN_ID, compared)
    assert summary.compared_organizations == compared
    state = summary.run.rates.outcomes
    assert (state.matched, state.only_in_civicpatch, state.only_in_civicpatch_not_compared) == (2, 2, 4)
    by_ocdid = {j.jurisdiction_ocdid: j.rates.outcomes for j in summary.jurisdictions}
    assert (by_ocdid[_BARRE].only_in_civicpatch, by_ocdid[_BARRE].only_in_civicpatch_not_compared) == (1, 4)
    assert (by_ocdid[_STOWE].only_in_civicpatch, by_ocdid[_STOWE].only_in_civicpatch_not_compared) == (1, 0)


def _refused(count: int) -> service.RowsOutsideState:
    rejected = [
        RejectedRow(source_row=row, jurisdiction_ocdid=f"{_BARRE}x", reason=RejectedReason.UNKNOWN_JURISDICTION)
        for row in range(2, 2 + count)
    ]
    return service.RowsOutsideState("vt", rejected)


@pytest.mark.unit
def test_a_refusal_lists_the_first_rows_and_counts_them_all():
    extra = 30
    refusal = _refused(service.MAX_REJECTED_LISTED + extra)

    assert len(refusal.listed) == service.MAX_REJECTED_LISTED
    assert len(refusal.rejected) == service.MAX_REJECTED_LISTED + extra
    assert f"and {extra} more" in str(refusal)


@pytest.mark.unit
def test_a_short_refusal_lists_every_row():
    refusal = _refused(2)

    assert [row.source_row for row in refusal.listed] == [2, 3]
    assert "more" not in str(refusal)
