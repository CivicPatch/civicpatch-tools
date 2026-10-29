"""HTTP-contract tests for roster comparisons: who may call them, and the shape that comes back.
The comparison itself is tested in tests/unit/core and the service in tests/integration."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import roster_comparisons as router
from schemas.common import Identity, UserRole
from schemas.roster_comparisons import (
    ComparedField,
    ComparisonRates,
    FieldFilter,
    JurisdictionRates,
    OutcomeCounts,
    PeopleFilter,
    PersonOutcome,
    RejectedReason,
    RejectedRow,
    RosterComparisonCreated,
    RosterComparisonDraft,
    RosterComparisonListItem,
    RosterComparisonListPage,
    RosterComparisonRun,
    RosterComparisonSummary,
    RunPeoplePage,
)
import services.roster_comparison_drafts as drafts_service
from services.roster_comparison import RowsOutsideState, RunNotFound

_PREFIX = "/roster-comparisons"
_RUN_ID = "11111111-1111-1111-1111-111111111111"
_BARRE = "ocd-jurisdiction/country:us/state:vt/place:barre/government"
_PAGE = "https://civicpatch.test/roster-comparisons/" + "11111111-1111-1111-1111-111111111111"
_UPLOAD = {
    "state": "vt",
    "source_columns": {"name": ["Official"]},
    "corrections": [],
    "rows": [{"source_row": 2, "jurisdiction_ocdid": _BARRE, "name": "Jane Doe"}],
}


def _identity(role: UserRole = UserRole.MAINTAINERS) -> Identity:
    return Identity(
        type="user_key",
        provider="supabase",
        provider_user_id="sb-1",
        email="m@example.com",
        role=role.value,
        user_id="00000000-0000-4000-8000-000000000001",
    )


def _client(identity: Identity | None = None) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: identity or _identity()
    app.include_router(router.get_router(), prefix=_PREFIX)
    return TestClient(app)


def _run() -> RosterComparisonRun:
    return RosterComparisonRun(
        id=_RUN_ID,
        state="vt",
        started_by_user_id="00000000-0000-4000-8000-000000000001",
        started_at="2026-10-22T14:05:00+00:00",
        source_columns={"name": ["Official"]},
        corrections=[],
        rates=ComparisonRates(outcomes=OutcomeCounts(matched=1)),
        jurisdictions_not_named=0,
    )


def _service(name: str, **kwargs):
    return patch(f"routers.api.roster_comparisons.service.{name}", new=AsyncMock(**kwargs))


@pytest.mark.unit
def test_an_upload_returns_the_runs_id_page_and_rates():
    created = RosterComparisonCreated(id=_RUN_ID, page_url=_PAGE, rates=_run().rates)
    with _service("run_roster_comparison", return_value=_RUN_ID) as run, _service(
        "get_run_created", return_value=created
    ):
        response = _client().post(_PREFIX, json=_UPLOAD)

    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["id"], data["page_url"]) == (_RUN_ID, _PAGE)
    assert data["rates"]["outcomes"]["matched"] == 1
    run.assert_awaited_once()


@pytest.mark.unit
def test_an_upload_without_corrections_is_refused_by_name():
    body = {key: value for key, value in _UPLOAD.items() if key != "corrections"}

    response = _client().post(_PREFIX, json=body)

    assert response.status_code == 422
    assert any(error["loc"][-1] == "corrections" for error in response.json()["detail"])


@pytest.mark.unit
def test_a_contributor_may_not_compare():
    response = _client(_identity(UserRole.CONTRIBUTORS)).post(_PREFIX, json=_UPLOAD)

    assert response.status_code == 403


@pytest.mark.unit
def test_runs_are_listed_a_page_at_a_time_each_with_its_page():
    item = RosterComparisonListItem(
        id=_RUN_ID,
        state="vt",
        started_at="2026-10-22T14:05:00+00:00",
        started_by="mango",
        jurisdictions_named=247,
        rates=_run().rates,
        page_url=_PAGE,
    )
    listed = RosterComparisonListPage(total_items=21, page=2, total_pages=2, data=[item])
    with _service("list_runs", return_value=listed) as list_runs:
        response = _client().get(_PREFIX, params={"page": 2, "per_page": 20})

    assert response.status_code == 200
    body = response.json()
    assert (body["total_items"], body["page"]) == (21, 2)
    assert (body["data"][0]["id"], body["data"][0]["page_url"]) == (_RUN_ID, _PAGE)
    list_runs.assert_awaited_once_with(2, 20)


@pytest.mark.unit
def test_a_contributor_may_not_list_runs():
    response = _client(_identity(UserRole.CONTRIBUTORS)).get(_PREFIX)

    assert response.status_code == 403


@pytest.mark.unit
def test_a_run_comes_back_with_its_page_and_jurisdictions():
    summary = RosterComparisonSummary(
        run=_run(),
        page_url=_PAGE,
        jurisdictions=[JurisdictionRates(jurisdiction_ocdid=_BARRE, rates=ComparisonRates())],
        organizations=[],
        compared_organizations=[],
    )
    with _service("get_run_summary", return_value=summary) as get_summary:
        response = _client().get(f"{_PREFIX}/{_RUN_ID}?organizations=Selectboard&organizations=Board+of+Listers")

    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["run"]["id"], data["page_url"]) == (_RUN_ID, _PAGE)
    assert [j["jurisdiction_ocdid"] for j in data["jurisdictions"]] == [_BARRE]
    get_summary.assert_awaited_once_with(_RUN_ID, ["Selectboard", "Board of Listers"])


@pytest.mark.unit
def test_an_unknown_run_is_404():
    with _service("get_run_people", side_effect=RunNotFound(_RUN_ID)):
        response = _client().get(f"{_PREFIX}/{_RUN_ID}/jurisdictions/{_BARRE}")

    assert response.status_code == 404


@pytest.mark.unit
def test_a_run_id_that_is_not_a_uuid_is_refused():
    response = _client().get(f"{_PREFIX}/not-a-run")

    assert response.status_code == 422


@pytest.mark.unit
def test_a_fields_people_are_paged_through_the_service():
    page = RunPeoplePage(total_items=120, page=2, total_pages=3, data=[])
    with _service("get_run_people_page", return_value=page) as get_page:
        response = _client().get(f"{_PREFIX}/{_RUN_ID}/people?field=emails&level=conflict&page=2&per_page=50")

    assert response.status_code == 200
    assert (response.json()["total_items"], response.json()["total_pages"]) == (120, 3)
    get_page.assert_awaited_once_with(
        _RUN_ID, PeopleFilter(field=ComparedField.EMAILS, level=FieldFilter.CONFLICT), None, 2, 50
    )


@pytest.mark.unit
def test_an_outcomes_people_are_paged_through_the_service():
    page = RunPeoplePage(total_items=61, page=1, total_pages=2, data=[])
    with _service("get_run_people_page", return_value=page) as get_page:
        response = _client().get(f"{_PREFIX}/{_RUN_ID}/people?outcome=only_in_uploaded_data&organizations=Selectboard")

    assert response.status_code == 200
    get_page.assert_awaited_once_with(
        _RUN_ID, PeopleFilter(outcome=PersonOutcome.ONLY_IN_UPLOADED_DATA), ["Selectboard"], 1, 50
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "query", ["field=emails&level=agreement", "field=emails", "level=conflict", "outcome=everyone"]
)
def test_a_bad_people_filter_is_refused(query: str):
    with _service("get_run_people_page") as get_page:
        response = _client().get(f"{_PREFIX}/{_RUN_ID}/people?{query}")

    assert response.status_code == 422
    get_page.assert_not_awaited()


# ── batched upload: drafts ────────────────────────────────────────────────────

_DRAFT_ID = "22222222-2222-2222-2222-222222222222"
_HEADER = {key: value for key, value in _UPLOAD.items() if key not in ("rows", "corrections")}


def _drafts(name: str, **kwargs):
    return patch(f"routers.api.roster_comparisons.drafts.{name}", new=AsyncMock(**kwargs))


def _draft(rows: int = 0) -> RosterComparisonDraft:
    return RosterComparisonDraft(id=_DRAFT_ID, rows=rows, expires_at="2026-10-24T14:05:00+00:00")


@pytest.mark.unit
def test_a_draft_starts_from_the_header_for_its_caller():
    with _drafts("start_draft", return_value=_draft()) as start:
        response = _client().post(f"{_PREFIX}/drafts", json=_HEADER)

    assert response.status_code == 200
    assert response.json()["data"]["id"] == _DRAFT_ID
    header, owner = start.await_args.args
    assert (header.state, owner) == ("vt", _identity().user_id)


@pytest.mark.unit
def test_a_batch_of_rows_is_added_to_the_draft():
    with _drafts("add_draft_rows", return_value=_draft(rows=1)) as add:
        response = _client().post(f"{_PREFIX}/drafts/{_DRAFT_ID}/rows", json={"rows": _UPLOAD["rows"]})

    assert response.status_code == 200
    assert response.json()["data"]["rows"] == 1
    draft_id, rows, owner = add.await_args.args
    assert (draft_id, len(rows), owner) == (_DRAFT_ID, 1, _identity().user_id)


@pytest.mark.unit
def test_a_batch_over_the_batch_size_is_refused():
    row = _UPLOAD["rows"][0]
    response = _client().post(f"{_PREFIX}/drafts/{_DRAFT_ID}/rows", json={"rows": [row] * 501})

    assert response.status_code == 422


@pytest.mark.unit
@pytest.mark.parametrize(
    ("error", "status"),
    [
        (lambda: drafts_service.DraftNotFound(_DRAFT_ID), 404),
        (drafts_service.DraftTooLarge, 413),
        (drafts_service.DraftIsEmpty, 422),
    ],
)
def test_draft_errors_reach_the_caller_as_statuses(error, status):
    with _drafts("finish_draft", side_effect=error()):
        response = _client().post(f"{_PREFIX}/drafts/{_DRAFT_ID}/finish", json={"corrections": []})

    assert response.status_code == status


@pytest.mark.unit
def test_a_finished_draft_returns_the_run_like_an_upload():
    created = RosterComparisonCreated(id=_RUN_ID, page_url=_PAGE, rates=_run().rates)
    with _drafts("finish_draft", return_value=created):
        response = _client().post(f"{_PREFIX}/drafts/{_DRAFT_ID}/finish", json={"corrections": []})

    assert response.status_code == 200
    assert response.json()["data"]["page_url"] == _PAGE


@pytest.mark.unit
def test_a_contributor_may_not_start_a_draft():
    response = _client(_identity(UserRole.CONTRIBUTORS)).post(f"{_PREFIX}/drafts", json=_HEADER)

    assert response.status_code == 403


def _outside_state(count: int) -> RowsOutsideState:
    rejected = [
        RejectedRow(source_row=row, jurisdiction_ocdid=f"{_BARRE}x", reason=RejectedReason.UNKNOWN_JURISDICTION)
        for row in range(2, 2 + count)
    ]
    return RowsOutsideState("vt", rejected)


@pytest.mark.unit
def test_an_upload_with_rows_outside_the_state_is_refused_with_them_listed():
    with _service("run_roster_comparison", side_effect=_outside_state(2)):
        response = _client().post(_PREFIX, json=_UPLOAD)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["rejected_count"] == 2
    assert [row["source_row"] for row in detail["rejected"]] == [2, 3]
    assert detail["message"].startswith("Not saved")


@pytest.mark.unit
def test_a_batch_with_rows_outside_the_state_is_refused_the_same_way():
    batch = {"rows": _UPLOAD["rows"]}
    with _drafts("add_draft_rows", side_effect=_outside_state(1)):
        response = _client().post(f"{_PREFIX}/drafts/{_DRAFT_ID}/rows", json=batch)

    assert response.status_code == 422
    assert response.json()["detail"]["rejected_count"] == 1


@pytest.mark.unit
def test_finishing_passes_the_complete_corrections():
    created = RosterComparisonCreated(id=_RUN_ID, page_url=_PAGE, rates=_run().rates)
    with _drafts("finish_draft", return_value=created) as finish:
        _client().post(f"{_PREFIX}/drafts/{_DRAFT_ID}/finish", json={"corrections": ["row 9: Montpellier to Montpelier"]})

    assert finish.await_args.args[2] == ["row 9: Montpellier to Montpelier"]


@pytest.mark.unit
def test_finishing_needs_the_corrections():
    with _drafts("finish_draft") as finish:
        response = _client().post(f"{_PREFIX}/drafts/{_DRAFT_ID}/finish")

    assert response.status_code == 422
    finish.assert_not_awaited()
