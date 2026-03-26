import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from psycopg.errors import UniqueViolation

<<<<<<< HEAD
from routers.api.review_sessions import _navigate_response


# ── _navigate_response ────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.asyncio
async def test_navigate_response_succeeds_first_try():
    result = {"request_id": "abc", "entry_number": 1, "has_more": True}
    with patch("routers.api.review_sessions.review_sessions_db.navigate_to_entry", new=AsyncMock(return_value=result)):
        response = await _navigate_response("session-1", 1)
    assert response == {"data": result}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_navigate_response_retries_on_unique_violation():
    result = {"request_id": "abc", "entry_number": 2, "has_more": False}
    mock = AsyncMock(side_effect=[UniqueViolation(), result])
    with patch("routers.api.review_sessions.review_sessions_db.navigate_to_entry", new=mock):
        response = await _navigate_response("session-1", 2)
    assert response == {"data": result}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_navigate_response_raises_409_on_second_unique_violation():
    mock = AsyncMock(side_effect=[UniqueViolation(), UniqueViolation()])
    with patch("routers.api.review_sessions.review_sessions_db.navigate_to_entry", new=mock):
        with pytest.raises(HTTPException) as exc_info:
            await _navigate_response("session-1", 1)
    assert exc_info.value.status_code == 409


@pytest.mark.unit
@pytest.mark.asyncio
async def test_navigate_response_raises_404_when_session_not_found():
    with patch("routers.api.review_sessions.review_sessions_db.navigate_to_entry", new=AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc_info:
            await _navigate_response("session-1", 1)
    assert exc_info.value.status_code == 404


@pytest.mark.unit
@pytest.mark.asyncio
async def test_navigate_response_returns_done_reason_when_goal_reached():
    with patch("routers.api.review_sessions.review_sessions_db.navigate_to_entry", new=AsyncMock(return_value={"done": "goal_reached"})):
        response = await _navigate_response("session-1", 11)
    assert response == {"data": None, "reason": "goal_reached"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_navigate_response_returns_done_reason_when_no_more_cards():
    with patch("routers.api.review_sessions.review_sessions_db.navigate_to_entry", new=AsyncMock(return_value={"done": "no_more_cards"})):
        response = await _navigate_response("session-1", 1)
    assert response == {"data": None, "reason": "no_more_cards"}
=======
>>>>>>> a0dc5bfe2 (Display markdown content with marked)
