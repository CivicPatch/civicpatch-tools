import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from database.pull_requests import get_pull_request_data_by_request_id
from shared.utils.statuses import RequestType


def _make_cursor(fetchone_return):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchone = AsyncMock(return_value=fetchone_return)
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
async def test_returns_none_when_not_found():
    cur = _make_cursor(None)
    with patch("database.pull_requests.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_pull_request_data_by_request_id("req-missing")
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_returns_row_for_open_pr():
    row = (
        "req-abc",          # request_id
        "https://github.com/org/repo/pull/42",  # url
        "open",             # status
        None,               # review_state
        42,                 # pr_number
        "ocd-jurisdiction/country:us/state:tx/place:austin/government",  # jurisdiction_ocdid
        "Austin",           # jurisdiction_name
        [{"name": "Jane Doe"}],  # data_json
        "https://austintexas.gov",  # jurisdiction_website_url
    )
    cur = _make_cursor(row)
    with patch("database.pull_requests.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_pull_request_data_by_request_id("req-abc")

    assert result is not None
    assert result["request_id"] == "req-abc"
    assert result["pr"]["status"] == "open"
    assert result["pr"]["number"] == 42
    assert result["jurisdiction_ocdid"] == "ocd-jurisdiction/country:us/state:tx/place:austin/government"
    assert result["jurisdiction_name"] == "Austin"
    assert result["proposed"] == [{"name": "Jane Doe"}]


@pytest.mark.asyncio
@pytest.mark.unit
async def test_returns_row_for_merged_pr():
    row = (
        "req-xyz",
        "https://github.com/org/repo/pull/99",
        "merged",
        None,
        99,
        "ocd-jurisdiction/country:us/state:ca/place:oakland/government",
        "Oakland",
        [],
        None,
    )
    cur = _make_cursor(row)
    with patch("database.pull_requests.get_pool", AsyncMock(return_value=_make_pool(cur))):
        result = await get_pull_request_data_by_request_id("req-xyz")

    assert result is not None
    assert result["pr"]["status"] == "merged"
    assert result["proposed"] == []


@pytest.mark.asyncio
@pytest.mark.unit
async def test_lookup_is_scoped_to_people_requests():
    """The pool filters decide what gets *offered*; this decides what a caller can
    *ask for*. Without the scope, deeplinking a jurisdiction edit's request_id would
    resolve as a review card with an empty roster and a Publish button."""
    cur = _make_cursor(None)
    with patch("database.pull_requests.get_pool", AsyncMock(return_value=_make_pool(cur))):
        await get_pull_request_data_by_request_id("req-abc")

    sql, params = cur.execute.await_args.args
    # Deny-list, not allow-list: request_type defaults to 'scrape' and legacy rows
    # use other values, so excluding by kind is the only safe direction.
    assert "r.request_type != %s" in sql
    assert params[1] == RequestType.JURISDICTION_MANUAL_EDIT
