import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from routers.api.review_sessions import _advance_with_retry, _enrich_entry


# ── _advance_with_retry ───────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_advance_with_retry_succeeds_first_try():
    result = {"job": {"request_id": "abc"}, "entry_number": 1}
    with patch("routers.api.review_sessions.review_sessions_db.advance_review_session", new=AsyncMock(return_value=result)):
        assert await _advance_with_retry("session-1") == result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_advance_with_retry_succeeds_on_second_try():
    result = {"job": {"request_id": "abc"}, "entry_number": 2}
    mock = AsyncMock(side_effect=[UniqueViolation(), result])
    with patch("routers.api.review_sessions.review_sessions_db.advance_review_session", new=mock):
        assert await _advance_with_retry("session-1") == result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_advance_with_retry_raises_409_on_second_unique_violation():
    mock = AsyncMock(side_effect=[UniqueViolation(), UniqueViolation()])
    with patch("routers.api.review_sessions.review_sessions_db.advance_review_session", new=mock):
        with pytest.raises(HTTPException) as exc_info:
            await _advance_with_retry("session-1")
    assert exc_info.value.status_code == 409


# ── _enrich_entry ─────────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_entry_returns_unchanged_when_no_jurisdiction_ocdid():
    entry = {"job": {"request_id": "abc"}}
    result = await _enrich_entry(entry)
    assert result == entry


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_entry_returns_unchanged_when_no_request_id():
    entry = {"job": {"jurisdiction_ocdid": "ocd-division/country:us/state:tx"}}
    result = await _enrich_entry(entry)
    assert result == entry


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_entry_enriches_when_both_fields_present():
    entry = {
        "job": {
            "request_id": "req-1",
            "jurisdiction_ocdid": "ocd-division/country:us/state:tx",
        }
    }
    people_data = {
        "req-1": {
            "existing": [{"name": "Alice"}],
            "pull_request": [{"title": "Update Alice"}],
        }
    }
    mock = AsyncMock(return_value=people_data)
    with patch("routers.api.review_sessions.database.people.get_people_data_by_request_ids", new=mock):
        result = await _enrich_entry(entry)

    assert result["existing"] == [{"name": "Alice"}]
    assert result["pull_request"] == [{"title": "Update Alice"}]
    assert result["job"] == entry["job"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enrich_entry_handles_missing_people_data():
    entry = {
        "job": {
            "request_id": "req-999",
            "jurisdiction_ocdid": "ocd-division/country:us/state:tx",
        }
    }
    mock = AsyncMock(return_value={})
    with patch("routers.api.review_sessions.database.people.get_people_data_by_request_ids", new=mock):
        result = await _enrich_entry(entry)

    assert result["existing"] == []
    assert result["pull_request"] == []
