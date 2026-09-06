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
import database.people as db_people
import database.review_pool as db_pull_requests
import database.changesets as db_requests
import database.issues as db_issues
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
    Updating a non-existent changeset_id must not raise — the UPDATE just
    matches zero rows. Exercises the dynamic SET clause builder.
    """
    await db_jobs.update_pipeline_run_status(
        run_id="00000000-0000-0000-0000-000000000000",
        status="pending",
        progress=0,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_pipeline_run_status_only_progress():
    """Exercises the branch where status is None (only progress in SET clause)."""
    await db_jobs.update_pipeline_run_status(
        run_id="00000000-0000-0000-0000-000000000000",
        progress=42,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_issues_page_no_filter():
    rows, total = await db_issues.get_issues_page(issue_types=[], page=1, per_page=10)
    assert isinstance(rows, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_issues_page_with_issue_types():
    """Exercises the IN clause and ORDER BY direction branches."""
    rows, total = await db_issues.get_issues_page(
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
async def test_get_people_by_jurisdictions_empty_inputs():
    assert await db_people.get_people_by_jurisdictions([]) == {}


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("view", ["quick", "detail"])
async def test_get_people_by_jurisdictions_builds_each_projection(view):
    """Both field sets are spliced into the SELECT, so both need real Postgres to parse."""
    result = await db_people.get_people_by_jurisdictions(
        ["ocd-jurisdiction/country:us/state:ca/place:oakland/government"], view=view
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# database.review_pool — dynamic WHERE clause
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_open_changesets_no_filter():
    rows, total, with_issues = await db_pull_requests.list_open_changesets()
    assert isinstance(rows, list)
    assert isinstance(total, int)
    assert isinstance(with_issues, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_open_changesets_by_state():
    """Exercises the state_code LIKE branch."""
    rows, total, with_issues = await db_pull_requests.list_open_changesets(state_code="ca")
    assert isinstance(rows, list)
    assert isinstance(total, int)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_list_open_changesets_by_jurisdiction():
    """Exercises the jurisdiction_ocdid = %s branch (takes priority over state_code)."""
    rows, total, with_issues = await db_pull_requests.list_open_changesets(
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
    _, result = await db_jurisdictions.get_jurisdiction_history(_FAKE_OCDID)
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_stale_jurisdictions():
    # Exercises the rolling-freshness/url/status predicates.
    result = await db_jurisdictions.get_stale_jurisdictions("zz")
    assert isinstance(result, list)


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
    result = await db_jobs.jurisdiction_ocdids_with_unfinished_runs()
    assert isinstance(result, set)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_pipeline_run_jurisdiction_ocdids_by_state():
    result = await db_jobs.jurisdiction_ocdids_with_unfinished_runs_in_state("zz")
    assert isinstance(result, set)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pipeline_run_status_not_found():
    result = await db_jobs.get_pipeline_run_status(_FAKE_UUID)
    assert result is None


# `get_pipeline_run_github_run_id` went with the column: 0 of 94 rows carried one and
# nothing in `pipelines/` ever called the endpoint that set it.


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
async def test_get_people_not_found():
    result = await db_people.get_roster(jurisdiction_ocdid=_FAKE_OCDID)
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_people_page_not_found():
    total, rows = await db_people.get_people_page(_FAKE_OCDID, limit=10, offset=0)
    assert isinstance(total, int)
    assert isinstance(rows, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_person_models_not_found():
    result = await db_people.get_person_models(_FAKE_OCDID)
    assert isinstance(result, list)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_people_by_state_not_found():
    result = await db_people.get_roster(state="zz")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# database.changesets — requests / pull requests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_changeset_jurisdiction_not_found():
    result = await db_requests.get_changeset_jurisdiction(_FAKE_UUID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_issue_changeset_details_empty():
    result = await db_requests.get_issue_changeset_details([])
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# database.issues — pipeline issues
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.integration
async def test_upsert_issue_unrecognized_role():
    """Exercises the INSERT ... ON CONFLICT path; catches placeholder count mismatches."""
    await db_issues.upsert_issue(
        "test-request-id",
        "unrecognized_role",
        [{"role": "grand_poobah", "person_name": "Alice"}],
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_issue_by_id_not_found():
    result = await db_issues.get_issue_by_id(_FAKE_UUID)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pending_issue_ocdids_by_state():
    result = await db_issues.jurisdiction_ocdids_with_pending_issues_in_state("zz")
    assert isinstance(result, set)


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
