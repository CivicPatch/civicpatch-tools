import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from database.people import get_people_data_by_request_ids


def _make_cursor(fetchall_side_effect):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchall = AsyncMock(side_effect=fetchall_side_effect)
    cur.__aenter__ = AsyncMock(return_value=cur)
    cur.__aexit__ = AsyncMock(return_value=False)
    return cur


def _make_pool(cursor):
    conn = AsyncMock()
    conn.cursor = MagicMock(return_value=cursor)
    conn.__aenter__ = AsyncMock(return_value=conn)
    conn.__aexit__ = AsyncMock(return_value=False)
    pool = AsyncMock()
    pool.connection = MagicMock(return_value=conn)
    return pool


@pytest.mark.asyncio
@pytest.mark.unit
async def test_returns_data_for_request_id():
    people_rows = [("ocd-jurisdiction/country:us/state:tx/place:austin/government", {"id": "p1", "name": "Jane Doe"})]
    jobs_rows = [
        ("req-1", [{"id": "p1", "name": "Jane Doe"}], "ocd-jurisdiction/country:us/state:tx/place:austin/government"),
    ]
    cur = _make_cursor([people_rows, jobs_rows])

    with patch("database.people.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_people_data_by_request_ids(
            ["ocd-jurisdiction/country:us/state:tx/place:austin/government"],
            ["req-1"],
        )

    assert "req-1" in result
    assert result["req-1"]["proposed"] == [{"id": "p1", "name": "Jane Doe"}]
    assert result["req-1"]["existing"] == [{"id": "p1", "name": "Jane Doe"}]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_returns_data_without_job_row():
    """Regression: PR whose request_id has no corresponding jobs row must still return data."""
    people_rows = []
    jobs_rows = [
        ("req-no-job", [{"id": "p2", "name": "Tom Lee"}], "ocd-jurisdiction/country:us/state:tx/place:oak_leaf/government"),
    ]
    cur = _make_cursor([people_rows, jobs_rows])

    with patch("database.people.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_people_data_by_request_ids(
            ["ocd-jurisdiction/country:us/state:tx/place:oak_leaf/government"],
            ["req-no-job"],
        )

    assert "req-no-job" in result
    assert result["req-no-job"]["proposed"] == [{"id": "p2", "name": "Tom Lee"}]
    assert result["req-no-job"]["existing"] == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_missing_request_id_not_in_result():
    """Request IDs not found in requests table produce no entry in the result."""
    cur = _make_cursor([[], []])

    with patch("database.people.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_people_data_by_request_ids(
            ["ocd-jurisdiction/x"],
            ["req-missing"],
        )

    assert result == {}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_multiple_prs_same_jurisdiction():
    """Multiple PRs for the same jurisdiction all receive the same existing people."""
    jur = "ocd-jurisdiction/country:us/state:tx/place:dallas/government"
    existing_person = {"id": "p1", "name": "Alice"}
    people_rows = [(jur, existing_person)]
    jobs_rows = [
        ("req-a", [{"id": "p2", "name": "Bob"}], jur),
        ("req-b", [{"id": "p3", "name": "Carol"}], jur),
    ]
    cur = _make_cursor([people_rows, jobs_rows])

    with patch("database.people.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_people_data_by_request_ids(["ocd-jurisdiction/x"], ["req-a", "req-b"])

    assert result["req-a"]["existing"] == [existing_person]
    assert result["req-b"]["existing"] == [existing_person]
    assert result["req-a"]["proposed"] == [{"id": "p2", "name": "Bob"}]
    assert result["req-b"]["proposed"] == [{"id": "p3", "name": "Carol"}]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_null_result_data_returns_empty_pull_request():
    """jsonb_agg returns None when result_data is empty — must be coerced to []."""
    jur = "ocd-jurisdiction/x"
    people_rows = []
    jobs_rows = [("req-empty", None, jur)]
    cur = _make_cursor([people_rows, jobs_rows])

    with patch("database.people.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_people_data_by_request_ids([jur], ["req-empty"])

    assert result["req-empty"]["proposed"] == []
