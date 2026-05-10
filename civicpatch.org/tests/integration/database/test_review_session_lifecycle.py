"""
Behavioral integration tests for review session lifecycle.

These tests verify observable outcomes against a real database — they do NOT
mock internals and will survive the FSM refactor unchanged.

Run with:
  mise run tcp-integration
"""
import uuid
import pytest
import pytest_asyncio
from database.database import get_pool
from database.review_sessions import create_or_get_review_session, get_active_review_session
from database.review_sessions import end_review_session
from database.review_session_entries import resolve_review_session_entries_by_request_id

_STATE_CODE = "zz"  # non-existent state, safe for test isolation


@pytest_asyncio.fixture
async def test_user():
    """Create a throw-away user, yield its UUID, clean up after."""
    provider_id = f"lifecycle-{uuid.uuid4().hex[:8]}"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (provider, provider_user_id, email)
            VALUES ('test', %s, %s)
            RETURNING id
            """,
            (provider_id, f"{provider_id}@test.com"),
        )
        row = await cur.fetchone()
        user_id = row[0]  # uuid.UUID object — works with UUID columns

    yield user_id

    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            DELETE FROM review_session_entries
            WHERE review_session_id IN (
                SELECT id FROM review_sessions WHERE user_id = %s
            )
            """,
            (user_id,),
        )
        await conn.execute("DELETE FROM review_sessions WHERE user_id = %s", (user_id,))
        await conn.execute(
            "DELETE FROM users WHERE provider = 'test' AND provider_user_id = %s",
            (provider_id,),
        )


async def _insert_entry(session_id: uuid.UUID, entry_number: int, status: str):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO review_session_entries
                (review_session_id, request_ids, jurisdiction_ocdid, status, entry_number)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                session_id,
                [f"00000000-0000-0000-cccc-{entry_number:012d}"],
                f"ocd-jurisdiction/country:us/state:zz/place:test_{entry_number}/government",
                status,
                entry_number,
            ),
        )


async def _count_entries(session_id: uuid.UUID, status: str | None = None) -> int:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        if status:
            await cur.execute(
                "SELECT COUNT(*) FROM review_session_entries WHERE review_session_id = %s AND status = %s",
                (session_id, status),
            )
        else:
            await cur.execute(
                "SELECT COUNT(*) FROM review_session_entries WHERE review_session_id = %s",
                (session_id,),
            )
        row = await cur.fetchone()
    return row[0]


async def _create_session(user_id: uuid.UUID) -> uuid.UUID:
    result = await create_or_get_review_session(str(user_id), _STATE_CODE, daily_goal=10)
    return uuid.UUID(result["id"])


# ── get_active_review_session ─────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_session_returns_none_when_only_resolved_entries(test_user):
    """
    The core bug: only resolved (merged) entries must NOT make a session appear active.
    A session is only active if it has claimed entries.
    """
    session_id = await _create_session(test_user)
    await _insert_entry(session_id, entry_number=1, status="resolved")
    await _insert_entry(session_id, entry_number=2, status="resolved")

    result = await get_active_review_session(str(test_user))
    assert result is None, "Session with only resolved entries must not appear active"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_session_returns_none_when_no_entries(test_user):
    """Fresh session with no entries must not appear active."""
    await _create_session(test_user)

    result = await get_active_review_session(str(test_user))
    assert result is None


# ── end_review_session ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_session_removes_claimed_entries_keeps_resolved(test_user):
    """
    end_review_session must purge claimed and passed entries but preserve
    resolved ones. Resolved entries tell the queue which jurisdictions have
    already been reviewed.
    """
    session_id = await _create_session(test_user)
    await _insert_entry(session_id, entry_number=1, status="resolved")
    await _insert_entry(session_id, entry_number=2, status="claimed")
    await _insert_entry(session_id, entry_number=3, status="passed")

    await end_review_session(str(session_id))

    assert await _count_entries(session_id) == 1, "Only resolved entry should remain"
    assert await _count_entries(session_id, "resolved") == 1
    assert await _count_entries(session_id, "claimed") == 0
    assert await _count_entries(session_id, "passed") == 0


# ── create_or_get_review_session ──────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_fresh_start_after_resolved_entries_uses_next_entry_number(test_user):
    """
    After resolved entries exist, next_entry_number must skip past them.
    This prevents new cards colliding with old resolved ones.
    """
    session_id = await _create_session(test_user)
    await _insert_entry(session_id, entry_number=1, status="resolved")
    await _insert_entry(session_id, entry_number=2, status="resolved")
    await _insert_entry(session_id, entry_number=3, status="resolved")

    result = await create_or_get_review_session(str(test_user), _STATE_CODE, daily_goal=10)

    assert result["next_entry_number"] == 4, (
        f"After 3 resolved entries, next_entry_number must be 4, got {result['next_entry_number']}"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fresh_session_with_no_history_starts_at_entry_1(test_user):
    """Brand new session with no prior entries must start at entry 1."""
    result = await create_or_get_review_session(str(test_user), _STATE_CODE, daily_goal=10)

    assert result["next_entry_number"] == 1


# ── reviewed_ocdids ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_session_resets_reviewed_ocdids(test_user):
    """end_review_session must clear reviewed_ocdids so the next session starts fresh."""
    pool = await get_pool()
    session_id = await _create_session(test_user)

    # Manually set some reviewed ocdids
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_sessions SET reviewed_ocdids = %s WHERE id = %s",
            (["ocd-jurisdiction/country:us/state:zz/place:test_1/government"], str(session_id)),
        )

    await end_review_session(str(session_id))

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT reviewed_ocdids FROM review_sessions WHERE id = %s", (str(session_id),))
        row = await cur.fetchone()
    assert row[0] == [], f"reviewed_ocdids must be empty after end_session, got {row[0]}"
