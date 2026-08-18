"""
Behavioral integration tests for 'saved' review session entries — a card the
reviewer committed to the branch but chose not to publish.

The contract under test: a saved card is held by its session (nobody else is
offered it, including the saving session itself) and returns to the pool only
when that session is released.

Run with:
  mise run tcp-integration
"""
import uuid
from datetime import timedelta

import pytest
import pytest_asyncio
from database.database import get_pool
from database.review_sessions import create_or_get_review_session, end_review_session
from database.review_session_entries import (
    purge_stale_idle_sessions,
    resolve_entries_for_request,
    save_entries_for_request,
)
from database.review_session_navigation import navigate_to_entry

_STATE_CODE = "zz"  # non-existent state, safe for test isolation


async def _create_user(prefix: str) -> tuple[uuid.UUID, str]:
    provider_id = f"{prefix}-{uuid.uuid4().hex[:8]}"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (provider, provider_user_id, email) VALUES ('test', %s, %s) RETURNING id",
            (provider_id, f"{provider_id}@test.com"),
        )
        row = await cur.fetchone()
    return row[0], provider_id  # type: ignore[index]


async def _delete_user(user_id: uuid.UUID, provider_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            DELETE FROM review_session_entries
            WHERE review_session_id IN (SELECT id FROM review_sessions WHERE user_id = %s)
            """,
            (user_id,),
        )
        await conn.execute("DELETE FROM review_sessions WHERE user_id = %s", (user_id,))
        await conn.execute("DELETE FROM users WHERE provider = 'test' AND provider_user_id = %s", (provider_id,))


@pytest_asyncio.fixture
async def reviewer():
    user_id, provider_id = await _create_user("saved-a")
    yield user_id
    await _delete_user(user_id, provider_id)


@pytest_asyncio.fixture
async def other_reviewer():
    user_id, provider_id = await _create_user("saved-b")
    yield user_id
    await _delete_user(user_id, provider_id)


@pytest_asyncio.fixture
async def open_pr():
    """An open, reviewable PR in state zz. Yields (request_id, ocdid)."""
    suffix = uuid.uuid4().hex[:8]
    ocdid = f"ocd-jurisdiction/country:us/state:zz/place:saved_{suffix}/government"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, status) VALUES (%s, 'active') ON CONFLICT DO NOTHING",
            (ocdid,),
        )
        await cur.execute(
            "INSERT INTO requests (jurisdiction_ocdid, data_json) VALUES (%s, %s) RETURNING id::text",
            (ocdid, '[{"id": "p1", "name": "Jane Doe"}]'),
        )
        request_id = (await cur.fetchone())[0]  # type: ignore[index]
        await cur.execute("INSERT INTO pipeline_runs (request_id, status) VALUES (%s, 'SUCCESS')", (request_id,))
        await cur.execute(
            "INSERT INTO pull_requests (request_id, pr_number, status) VALUES (%s, %s, 'open')",
            (request_id, 991000),
        )

    yield request_id, ocdid

    async with pool.connection() as conn:
        await conn.execute("DELETE FROM pull_requests WHERE request_id::text = %s", (request_id,))
        await conn.execute("DELETE FROM pipeline_runs WHERE request_id::text = %s", (request_id,))
        await conn.execute("DELETE FROM requests WHERE id::text = %s", (request_id,))
        await conn.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))


async def _create_session(user_id: uuid.UUID) -> str:
    result = await create_or_get_review_session(str(user_id), _STATE_CODE, daily_goal=10)
    return result["id"]


async def _insert_entry(session_id: str, entry_number: int, status: str, request_id: str, ocdid: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO review_session_entries
                (review_session_id, request_ids, jurisdiction_ocdid, status, entry_number)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (session_id, [request_id], ocdid, status, entry_number),
        )


async def _entry_status(session_id: str, entry_number: int) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT status FROM review_session_entries WHERE review_session_id = %s AND entry_number = %s",
            (session_id, entry_number),
        )
        row = await cur.fetchone()
    return row[0] if row else None


async def _age_entries(session_id: str, minutes: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_session_entries SET created_at = NOW() - %s WHERE review_session_id = %s",
            (timedelta(minutes=minutes), session_id),
        )


# ── the hold ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_saved_card_is_not_reoffered_to_its_own_session(reviewer, open_pr):
    """
    Saving must take the card off this reviewer's queue. It stays in the pool
    (unpublished), so without the hold it would be handed straight back.
    """
    request_id, ocdid = open_pr
    session_id = await _create_session(reviewer)
    await _insert_entry(session_id, 1, "claimed", request_id, ocdid)

    await save_entries_for_request(request_id)

    result = await navigate_to_entry(session_id, 2)
    assert result is not None
    assert result.get("request_id") != request_id, "A saved card must not be re-offered later in the same session"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_saved_card_is_held_from_another_reviewers_session(reviewer, other_reviewer, open_pr):
    """A saved card belongs to its session — another reviewer must not be offered it."""
    request_id, ocdid = open_pr
    session_id = await _create_session(reviewer)
    await _insert_entry(session_id, 1, "claimed", request_id, ocdid)
    await save_entries_for_request(request_id)

    other_session = await _create_session(other_reviewer)
    result = await navigate_to_entry(other_session, 1)

    assert result is not None
    assert result.get("request_id") != request_id, "Another reviewer must not be offered a card saved by a live session"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_saved_card_returns_to_the_pool_once_the_session_ends(reviewer, other_reviewer, open_pr):
    """The hold lasts exactly as long as the session does."""
    request_id, ocdid = open_pr
    session_id = await _create_session(reviewer)
    await _insert_entry(session_id, 1, "claimed", request_id, ocdid)
    await save_entries_for_request(request_id)

    await end_review_session(session_id)

    other_session = await _create_session(other_reviewer)
    result = await navigate_to_entry(other_session, 1)

    assert result is not None
    assert result.get("request_id") == request_id, "Ending the session must release the saved card back to the pool"


# ── the sweeps ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_entry_age_sweep_releases_a_claimed_card_but_not_a_saved_one(reviewer, other_reviewer, open_pr):
    """
    _cleanup_stale_entries (which runs on every other session's navigate) keys on
    the entry's own age, not on session activity. Exempting 'saved' is what stops
    it handing a saved card to another reviewer mid-session.
    """
    request_id, ocdid = open_pr
    session_id = await _create_session(reviewer)
    await _insert_entry(session_id, 1, "claimed", request_id, ocdid)
    await _insert_entry(session_id, 2, "saved", f"{uuid.uuid4()}", f"{ocdid}_two")
    await _age_entries(session_id, minutes=40)

    # Another session navigating is what triggers the sweep.
    other_session = await _create_session(other_reviewer)
    await navigate_to_entry(other_session, 1)

    assert await _entry_status(session_id, 1) is None, "A stale claimed entry must be swept"
    assert await _entry_status(session_id, 2) == "saved", "A saved entry must survive the entry-age sweep"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_idle_session_sweep_releases_saved_cards(reviewer, open_pr):
    """
    The saved hold must not be permanent: once the *session* goes idle,
    purge_stale_idle_sessions releases it like any other unresolved entry.
    """
    request_id, ocdid = open_pr
    session_id = await _create_session(reviewer)
    await _insert_entry(session_id, 1, "claimed", request_id, ocdid)
    await save_entries_for_request(request_id)

    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_sessions SET updated_at = NOW() - INTERVAL '40 minutes' WHERE id = %s",
            (session_id,),
        )

    await purge_stale_idle_sessions()

    assert await _entry_status(session_id, 1) is None, "An idle session's saved entry must be released"


# ── status transitions ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_saving_twice_is_a_no_op(reviewer, open_pr):
    request_id, ocdid = open_pr
    session_id = await _create_session(reviewer)
    await _insert_entry(session_id, 1, "claimed", request_id, ocdid)

    await save_entries_for_request(request_id)
    await save_entries_for_request(request_id)

    assert await _entry_status(session_id, 1) == "saved"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publishing_a_saved_card_promotes_it_to_resolved(reviewer, open_pr):
    """Back-navigating to a saved card and publishing it must credit the review."""
    request_id, ocdid = open_pr
    session_id = await _create_session(reviewer)
    await _insert_entry(session_id, 1, "claimed", request_id, ocdid)
    await save_entries_for_request(request_id)

    await resolve_entries_for_request(request_id)

    assert await _entry_status(session_id, 1) == "resolved"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_saving_does_not_downgrade_a_resolved_entry(reviewer, open_pr):
    request_id, ocdid = open_pr
    session_id = await _create_session(reviewer)
    await _insert_entry(session_id, 1, "resolved", request_id, ocdid)

    await save_entries_for_request(request_id)

    assert await _entry_status(session_id, 1) == "resolved"
