"""
Integration tests for database functions that use dynamic SQL construction.

These tests execute against the real dev database. Their purpose is not to assert
specific row counts or data — it's to prove the SQL compiles and executes without
error before and after the sql.SQL() composition refactor.

Run with:
  mise run tapi -- -m integration
"""
import pytest

import database.database as db
import database.people as db_people
import database.pull_requests as db_pull_requests


# ---------------------------------------------------------------------------
# database.database — dynamic WHERE / SET clause functions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_jurisdictions_no_filter():
    total, rows = await db.search_jurisdictions(state="ca")
    assert isinstance(total, int)
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_jurisdictions_with_search_string():
    """Exercises the branch that appends a LIKE clause to the WHERE list."""
    total, rows = await db.search_jurisdictions(state="ca", search_string="oak")
    assert isinstance(total, int)
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_jurisdictions_with_pagination():
    total, rows = await db.search_jurisdictions(state="ca", limit=5, skip=0)
    assert isinstance(total, int)
    assert len(rows) <= 5


@pytest.mark.asyncio
@pytest.mark.integration
async def test_count_jobs_with_errors_no_filter():
    result = await db.count_jobs_with_errors()
    assert isinstance(result, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_count_jobs_with_errors_with_state():
    """Exercises the branch that appends a LIKE clause."""
    result = await db.count_jobs_with_errors(state_code="ca")
    assert isinstance(result, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jobs_with_errors_no_filter():
    rows = await db.get_jobs_with_errors()
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jobs_with_errors_with_state():
    rows = await db.get_jobs_with_errors(state_code="ca")
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_job_status_nonexistent_request_is_noop():
    """
    Updating a non-existent request_id must not raise — the UPDATE just
    matches zero rows. Exercises the dynamic SET clause builder.
    """
    await db.update_job_status(
        request_id="00000000-0000-0000-0000-000000000000",
        status="pending",
        progress=0,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_job_status_only_progress():
    """Exercises the branch where status is None (only progress in SET clause)."""
    await db.update_job_status(
        request_id="00000000-0000-0000-0000-000000000000",
        progress=42,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_requests_for_export_no_date_filter():
    rows = await db.get_requests_for_export(state="ca", from_date=None, to_date=None)
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_requests_for_export_with_date_range():
    """Exercises both from_date and to_date appended to date_clauses."""
    rows = await db.get_requests_for_export(
        state="ca",
        from_date="2024-01-01",
        to_date="2099-12-31",
    )
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_unrecognized_roles_no_filter():
    rows = await db.get_unrecognized_roles()
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_unrecognized_roles_with_state():
    rows = await db.get_unrecognized_roles(state_code="ca")
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_events_page_no_filter():
    rows, total = await db.get_job_events_page(event_types=[], page=1, per_page=10)
    assert isinstance(rows, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_events_page_with_event_types():
    """Exercises the IN clause and ORDER BY direction branches."""
    rows, total = await db.get_job_events_page(
        event_types=["unrecognized_role"],
        page=1,
        per_page=5,
        sort_desc=False,
    )
    assert isinstance(rows, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_events_no_filter():
    rows = await db.get_job_events(event_type="unrecognized_role")
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_job_events_with_state():
    rows = await db.get_job_events(event_type="unrecognized_role", state_code="ca")
    assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# database.people — dynamic projection columns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_people_data_by_request_ids_empty_inputs():
    result = await db_people.get_people_data_by_request_ids(
        jurisdiction_ocdids=[],
        request_ids=[],
    )
    assert isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_people_data_by_request_ids_quick_view():
    result = await db_people.get_people_data_by_request_ids(
        jurisdiction_ocdids=["ocd-jurisdiction/country:us/state:ca/place:oakland/government"],
        request_ids=["00000000-0000-0000-0000-000000000000"],
        view="quick",
    )
    assert isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_people_data_by_request_ids_detail_view():
    """Exercises the detail field set (larger projection)."""
    result = await db_people.get_people_data_by_request_ids(
        jurisdiction_ocdids=["ocd-jurisdiction/country:us/state:ca/place:oakland/government"],
        request_ids=["00000000-0000-0000-0000-000000000000"],
        view="detail",
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# database.pull_requests — dynamic WHERE clause
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_open_pull_requests_no_filter():
    rows, total, with_issues = await db_pull_requests.list_open_pull_requests()
    assert isinstance(rows, list)
    assert isinstance(total, int)
    assert isinstance(with_issues, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_open_pull_requests_by_state():
    """Exercises the state_code LIKE branch."""
    rows, total, with_issues = await db_pull_requests.list_open_pull_requests(state_code="ca")
    assert isinstance(rows, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_open_pull_requests_by_jurisdiction():
    """Exercises the jurisdiction_ocdid = %s branch (takes priority over state_code)."""
    rows, total, with_issues = await db_pull_requests.list_open_pull_requests(
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:ca/place:oakland/government"
    )
    assert isinstance(rows, list)
    assert isinstance(total, int)
