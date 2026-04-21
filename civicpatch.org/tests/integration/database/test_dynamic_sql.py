"""
Integration tests for database functions.

These tests execute against the real test database. Their purpose is not to assert
specific row counts or data — it's to prove the SQL compiles and executes without
error, and that return types are correct. They serve as a safety net for structural
refactors that move functions between modules.

Run with:
  mise run tcp-integration
"""
import pytest

import database.jurisdictions as db_jurisdictions
import database.pipeline_runs as db_jobs
import database.notes as db_notes
import database.people as db_people
import database.pull_requests as db_pull_requests
import database.requests as db_requests
import database.pipeline_issues as db_pipeline_issues
import database.summary as db_summary
import database.users as db_users

_FAKE_UUID = "00000000-0000-0000-0000-000000000000"
_FAKE_OCDID = "ocd-jurisdiction/country:us/state:zz/place:nowhere/government"


# ---------------------------------------------------------------------------
# database.jurisdictions — dynamic WHERE / SET clause functions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_jurisdictions_no_filter():
    total, rows = await db_jurisdictions.search_jurisdictions(state="ca")
    assert isinstance(total, int)
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_jurisdictions_with_search_string():
    """Exercises the branch that appends a LIKE clause to the WHERE list."""
    total, rows = await db_jurisdictions.search_jurisdictions(state="ca", search_string="oak")
    assert isinstance(total, int)
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_jurisdictions_with_pagination():
    total, rows = await db_jurisdictions.search_jurisdictions(state="ca", limit=5, skip=0)
    assert isinstance(total, int)
    assert len(rows) <= 5


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_pipeline_run_status_nonexistent_request_is_noop():
    """
    Updating a non-existent request_id must not raise — the UPDATE just
    matches zero rows. Exercises the dynamic SET clause builder.
    """
    await db_jobs.update_pipeline_run_status(
        request_id="00000000-0000-0000-0000-000000000000",
        status="pending",
        progress=0,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_pipeline_run_status_only_progress():
    """Exercises the branch where status is None (only progress in SET clause)."""
    await db_jobs.update_pipeline_run_status(
        request_id="00000000-0000-0000-0000-000000000000",
        progress=42,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_requests_for_export_no_date_filter():
    rows = await db_requests.get_requests_for_export(state="ca", from_date=None, to_date=None)
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_requests_for_export_with_date_range():
    """Exercises both from_date and to_date appended to date_clauses."""
    rows = await db_requests.get_requests_for_export(
        state="ca",
        from_date="2024-01-01",
        to_date="2099-12-31",
    )
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_unrecognized_roles_grouped():
    rows = await db_pipeline_issues.get_unrecognized_roles_grouped()
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_issues_page_no_filter():
    rows, total = await db_pipeline_issues.get_pipeline_issues_page(issue_types=[], page=1, per_page=10)
    assert isinstance(rows, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_issues_page_with_issue_types():
    """Exercises the IN clause and ORDER BY direction branches."""
    rows, total = await db_pipeline_issues.get_pipeline_issues_page(
        issue_types=["unrecognized_role"],
        page=1,
        per_page=5,
        sort_desc=False,
    )
    assert isinstance(rows, list)
    assert isinstance(total, int)


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


# ---------------------------------------------------------------------------
# database.users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_not_found():
    result = await db_users.get_user("github", "nonexistent-user-99999")
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_by_api_key_not_found():
    result = await db_users.get_user_by_api_key("fake-api-key-that-does-not-exist")
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_by_api_key_id_not_found():
    result = await db_users.get_user_by_api_key_id(0)  # api_key_id is an integer
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_api_keys_for_user_not_found():
    result = await db_users.get_api_keys_for_user("github", "nonexistent-user-99999")
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_id_by_provider_not_found():
    result = await db_users.get_user_id_by_provider("github", "nonexistent-user-99999")
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_api_usage_for_user_not_found():
    """Returns zeros when no usage limit row exists for the user."""
    result = await db_users.get_api_usage_for_user("github", "nonexistent-user-99999")
    assert isinstance(result, dict)
    assert "daily_limit" in result
    assert "usage_count" in result


# ---------------------------------------------------------------------------
# database.jurisdictions — jurisdictions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_states():
    result = await db_jurisdictions.get_states()
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jurisdiction_not_found():
    result = await db_jurisdictions.get_jurisdiction(_FAKE_OCDID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jurisdiction_geom_not_found():
    result = await db_jurisdictions.get_jurisdiction_geom(_FAKE_OCDID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jurisdictions_by_ocdids_empty():
    result = await db_jurisdictions.get_jurisdictions_by_ocdids([])
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jurisdiction_history_not_found():
    result = await db_jurisdictions.get_jurisdiction_history(_FAKE_OCDID)
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jurisdiction_updates():
    result = await db_jurisdictions.get_jurisdiction_updates()
    assert isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_geojson_by_latlong():
    result = await db_jurisdictions.get_geojson_by_latlong(37.8, -122.3)
    assert isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_people_by_geo():
    result = await db_jurisdictions.get_people_by_geo(37.8, -122.3)
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# database.pipeline_runs — pipeline runs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_pipeline_runs():
    result = await db_jobs.list_pipeline_runs()
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_run_not_found():
    result = await db_jobs.get_pipeline_run(_FAKE_UUID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_pipeline_runs():
    rows, total = await db_jobs.get_active_pipeline_runs()
    assert isinstance(rows, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_pipeline_runs_with_state():
    rows, total = await db_jobs.get_active_pipeline_runs(state_code="ca")
    assert isinstance(rows, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_pipeline_run_jurisdiction_ocdids():
    result = await db_jobs.get_active_pipeline_run_jurisdiction_ocdids()
    assert isinstance(result, set)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_run_status_not_found():
    result = await db_jobs.get_pipeline_run_status(_FAKE_UUID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_run_github_run_id_not_found():
    result = await db_jobs.get_pipeline_run_github_run_id(_FAKE_UUID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_run_data_json_not_found():
    result = await db_jobs.get_pipeline_run_data_json(_FAKE_UUID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_run_result_not_found():
    result = await db_jobs.get_pipeline_run_result(_FAKE_UUID)
    assert result is None


# ---------------------------------------------------------------------------
# database.people — people
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_filter_existing_person_ids_empty():
    result = await db_people.filter_existing_person_ids([])
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_jurisdiction_people_not_found():
    result = await db_people.get_jurisdiction_people(_FAKE_OCDID)
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_all_people_for_jurisdiction_not_found():
    total, rows = await db_people.get_all_people_for_jurisdiction(_FAKE_OCDID, limit=10, offset=0)
    assert isinstance(total, int)
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_people_for_jurisdiction_not_found():
    result = await db_people.get_people_for_jurisdiction(_FAKE_OCDID)
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_people_by_state_not_found():
    result = await db_people.get_people_by_state("zz")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# database.requests — requests / pull requests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_request_jurisdiction_not_found():
    result = await db_requests.get_request_jurisdiction(_FAKE_UUID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_issue_request_details_empty():
    result = await db_requests.get_issue_request_details([])
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_open_pr_request_ids():
    result = await db_pull_requests.get_open_pr_request_ids()
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# database.pipeline_issues — pipeline issues
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_upsert_pipeline_issue_unrecognized_role():
    """Exercises the INSERT ... ON CONFLICT path; catches placeholder count mismatches."""
    await db_pipeline_issues.upsert_pipeline_issue(
        "test-request-id",
        "unrecognized_role",
        "issue",
        [{"role": "grand_poobah", "person_name": "Alice"}],
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upsert_pipeline_issue_conflict_preserves_pr_opened():
    """A new request for an issue already in pr_opened must not reset it to pending."""
    from shared.utils.statuses import PipelineIssueStatus

    await db_pipeline_issues.upsert_pipeline_issue(
        "test-request-id-1",
        "unrecognized_role",
        "issue",
        [{"role": "archduke", "person_name": "Bob"}],
    )

    # Simulate the issue having a PR opened for it
    from database.database import get_pool
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE pipeline_issues SET status = %s WHERE issue_type = %s AND issue_key = %s",
            (PipelineIssueStatus.PR_OPENED, "unrecognized_role", "archduke"),
        )

    # New request for the same role — must not clobber pr_opened
    await db_pipeline_issues.upsert_pipeline_issue(
        "test-request-id-2",
        "unrecognized_role",
        "issue",
        [{"role": "archduke", "person_name": "Carol"}],
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT status FROM pipeline_issues WHERE issue_type = %s AND issue_key = %s",
            ("unrecognized_role", "archduke"),
        )
        row = await cur.fetchone()
    assert row is not None
    assert row[0] == PipelineIssueStatus.PR_OPENED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_issue_by_id_not_found():
    result = await db_pipeline_issues.get_pipeline_issue_by_id(_FAKE_UUID)
    assert result is None


# ---------------------------------------------------------------------------
# database.notes — notes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_notes_for_jurisdiction_not_found():
    total, notes = await db_notes.get_notes_for_jurisdiction(_FAKE_OCDID, limit=10, offset=0)
    assert isinstance(total, int)
    assert isinstance(notes, list)


# ---------------------------------------------------------------------------
# database.summary — summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_summary_counts():
    result = await db_summary.get_summary_counts(include_issues=True)
    assert isinstance(result, dict)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_summary_counts_without_issues():
    result = await db_summary.get_summary_counts(include_issues=False)
    assert isinstance(result, dict)
