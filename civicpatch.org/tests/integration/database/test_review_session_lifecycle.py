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
from database.dismissals import mark_dismissed
from shared.utils.statuses import DismissalReason
from database.review_sessions import create_or_get_review_session, get_active_review_session
from database.review_sessions import end_review_session
from database.publications import publish_changeset
from database.review_pool import list_open_changesets
from database.issues import create_user_reported_issue, resolve_issue
from database.review_session_navigation import navigate_to_entry

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
                (review_session_id, changeset_ids, jurisdiction_ocdid, status, entry_number)
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


async def _seed_open_pr(suffix: str) -> tuple[str, str]:
    """Insert a jurisdiction + request + pipeline_run + open pull_request in state zz. Returns (changeset_id, ocdid)."""
    ocdid = f"ocd-jurisdiction/country:us/state:zz/place:pool_{suffix}/government"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, status) VALUES (%s, 'active') ON CONFLICT DO NOTHING",
            (ocdid,),
        )
        await cur.execute(
            "INSERT INTO changesets (kind, jurisdiction_ocdid) "
            "VALUES ('scrape', %s) RETURNING id::text",
            (ocdid,),
        )
        changeset_id = (await cur.fetchone())[0]
        await cur.execute(
            # The review pool is "this scrape saw somebody" — one sighting is a roster.
            "INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label, source_url) "
            "VALUES (%s, %s, 'Jane Doe', 'Mayor', 'https://zz.gov/council')",
            (changeset_id, ocdid),
        )
        await cur.execute(
            "UPDATE changesets SET "
            "updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (changeset_id,),
        )
    return changeset_id, ocdid


async def _cleanup_open_pr(changeset_id: str, ocdid: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        # The run lives on the request now; deleting the request takes it.
        await conn.execute("DELETE FROM changesets WHERE id::text = %s", (changeset_id,))
        await conn.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))


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

    result = await get_active_review_session(str(test_user), _STATE_CODE)
    assert result is None, "Session with only resolved entries must not appear active"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_session_returns_none_when_no_entries(test_user):
    """Fresh session with no entries must not appear active."""
    await _create_session(test_user)

    result = await get_active_review_session(str(test_user), _STATE_CODE)
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


# ── end → start gives a fresh session ─────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_end_session_then_create_starts_fresh_session(test_user):
    # end_review_session marks the old row with ended_at and purges its non-resolved
    # entries; the next create_or_get inserts a brand-new row starting at entry 1. The
    # user-facing guarantee is "next session starts fresh."
    pool = await get_pool()
    session_a_id = await _create_session(test_user)

    await _insert_entry(session_a_id, entry_number=1, status="resolved")
    await _insert_entry(session_a_id, entry_number=2, status="claimed")

    await end_review_session(str(session_a_id))

    session_b = await create_or_get_review_session(str(test_user), _STATE_CODE, daily_goal=10)
    assert session_b["id"] != str(session_a_id), "End must force a brand-new session row"
    assert session_b["next_entry_number"] == 1, "Fresh session must start at entry 1"

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT ended_at FROM review_sessions WHERE id = %s",
            (str(session_a_id),),
        )
        old = await cur.fetchone()
        assert old[0] is not None, "Old session must be marked ended"

        await cur.execute(
            "SELECT status FROM review_session_entries WHERE review_session_id = %s ORDER BY entry_number",
            (str(session_a_id),),
        )
        statuses = [r[0] for r in await cur.fetchall()]
        assert statuses == ["resolved"], "Only resolved entries should remain on the ended session"


# ── updated_at threshold (new behaviour after status removal) ─────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_resumes_when_session_updated_at_is_recent(test_user):
    """
    A session whose updated_at is within the idle window must not be purged
    when create_or_get_review_session is called again.
    """
    pool = await get_pool()
    session_id = await _create_session(test_user)
    await _insert_entry(session_id, entry_number=1, status="claimed")

    # Simulate a session that was active 20 minutes ago
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_sessions SET updated_at = NOW() - INTERVAL '20 minutes' WHERE id = %s",
            (session_id,),
        )

    await create_or_get_review_session(str(test_user), _STATE_CODE, daily_goal=10)

    assert await _count_entries(session_id, "claimed") == 1, (
        "Claimed entry must survive when session updated_at is within idle window"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_purges_when_session_updated_at_is_stale(test_user):
    """
    A session whose updated_at is outside the idle window must be purged
    (claimed entries deleted) when create_or_get_review_session is called again.
    """
    pool = await get_pool()
    session_id = await _create_session(test_user)
    await _insert_entry(session_id, entry_number=1, status="claimed")

    # Simulate an abandoned session from 40 minutes ago
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_sessions SET updated_at = NOW() - INTERVAL '40 minutes' WHERE id = %s",
            (session_id,),
        )

    await create_or_get_review_session(str(test_user), _STATE_CODE, daily_goal=10)

    assert await _count_entries(session_id, "claimed") == 0, (
        "Claimed entry must be purged when session updated_at is past idle window"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_cleanup_releases_stale_claimed_entry(test_user):
    """
    purge_stale_idle_sessions must delete claimed entries from sessions
    whose updated_at is past the idle window, unblocking that jurisdiction.
    """
    from database.review_session_entries import purge_stale_idle_sessions

    pool = await get_pool()
    session_id = await _create_session(test_user)
    await _insert_entry(session_id, entry_number=1, status="claimed")

    # Mark the session as stale
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_sessions SET updated_at = NOW() - INTERVAL '40 minutes' WHERE id = %s",
            (session_id,),
        )

    result = await purge_stale_idle_sessions()

    assert result["entries_deleted"] >= 1, "Cleanup must delete at least the stale claimed entry"
    assert await _count_entries(session_id, "claimed") == 0, (
        "Claimed entry must be gone after cleanup so the jurisdiction is unblocked"
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_sessions_cannot_claim_same_jurisdiction(test_user):
    """
    The unique partial index on active claims must prevent two sessions from
    claiming the same jurisdiction simultaneously. The second INSERT must raise
    UniqueViolation (which the router retries with a different card).
    """
    import uuid
    from psycopg.errors import UniqueViolation

    pool = await get_pool()
    session_a = await _create_session(test_user)
    ocdid = f"ocd-jurisdiction/country:us/state:zz/place:contested/government"

    # Session A claims the jurisdiction
    await _insert_entry(session_a, entry_number=1, status="claimed")

    # Overwrite with the shared ocdid for a deterministic collision
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE review_session_entries SET jurisdiction_ocdid = %s WHERE review_session_id = %s",
            (ocdid, session_a),
        )

    # Session B from a second user tries to claim the same jurisdiction
    provider_id = f"concurrent-{uuid.uuid4().hex[:8]}"
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (provider, provider_user_id, email) VALUES ('test', %s, %s) RETURNING id",
            (provider_id, f"{provider_id}@test.com"),
        )
        user_b = (await cur.fetchone())[0]

    try:
        session_b = await _create_session(user_b)
        async with pool.connection() as conn:
            with pytest.raises(UniqueViolation):
                await conn.execute(
                    """
                    INSERT INTO review_session_entries
                        (review_session_id, changeset_ids, jurisdiction_ocdid, status, entry_number)
                    VALUES (%s, %s, %s, 'claimed', 1)
                    """,
                    (session_b, ["00000000-0000-0000-cccc-000000000099"], ocdid),
                )
    finally:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM review_session_entries WHERE review_session_id IN (SELECT id FROM review_sessions WHERE user_id = %s)",
                (user_b,),
            )
            await conn.execute("DELETE FROM review_sessions WHERE user_id = %s", (user_b,))
            await conn.execute("DELETE FROM users WHERE provider = 'test' AND provider_user_id = %s", (provider_id,))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_active_session_returns_none_after_end_session(test_user):
    """
    After end_review_session purges claimed entries, get_active_review_session
    must return None — the session is no longer resumable.
    """
    session_id = await _create_session(test_user)
    await _insert_entry(session_id, entry_number=1, status="claimed")

    await end_review_session(str(session_id))

    result = await get_active_review_session(str(test_user), _STATE_CODE)
    assert result is None, (
        "Session must not appear active after end_review_session — claimed entries were purged"
    )


# ── availability pool: publishing removes a card, permanently ─────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_publishing_removes_the_card_from_the_pool_for_good():
    """
    Publishing takes a scrape out of the review pool and it never comes back.

    This used to be a *park*: publishing set merge_enqueued_at, which had to survive a failed
    merge or the PR was re-offered, and an admin dismissing the merge_failed issue un-parked
    it. Migration 115 made publish state a fact on the request instead of a flag on a PR, so
    there is nothing to un-park — and the regression the park guarded against (an already
    published scrape reappearing) is now impossible rather than defended.
    """
    changeset_id, ocdid = await _seed_open_pr("x")
    try:
        before, _, _ = await list_open_changesets(state_code="zz")
        assert changeset_id in [r["changeset_id"] for r in before], "unpublished scrape starts in the pool"

        await publish_changeset(changeset_id, ocdid, [])

        after, _, _ = await list_open_changesets(state_code="zz")
        assert changeset_id not in [r["changeset_id"] for r in after], "published scrape must leave the pool"
    finally:
        await _cleanup_open_pr(changeset_id, ocdid)


# ── availability pool: a reported issue parks a PR until the issue is resolved ──

@pytest.mark.asyncio
@pytest.mark.integration
async def test_reported_pr_leaves_pool_until_issue_resolved():
    """
    Reporting an issue against a review removes its PR from the pool while the issue is live,
    and it returns once the issue reaches a terminal state (here, an admin resolving it).
    """
    changeset_id, ocdid = await _seed_open_pr("reported")
    try:
        before, _, _ = await list_open_changesets(state_code="zz")
        assert changeset_id in [r["changeset_id"] for r in before], "open PR should start in the pool"

        issue_id = await create_user_reported_issue(
            changeset_id, "title", "body", "https://github.com/x/y/issues/1", 1, str(uuid.uuid4())
        )
        reported, _, _ = await list_open_changesets(state_code="zz")
        assert changeset_id not in [r["changeset_id"] for r in reported], "reported PR must leave the pool"

        await resolve_issue(issue_id)
        after, _, _ = await list_open_changesets(state_code="zz")
        assert changeset_id in [r["changeset_id"] for r in after], "PR returns to the pool once the issue is resolved"
    finally:
        pool = await get_pool()
        async with pool.connection() as conn:
            await conn.execute("DELETE FROM issues WHERE %s = ANY(changeset_ids)", (changeset_id,))
        await _cleanup_open_pr(changeset_id, ocdid)


# ── navigation: has_next respects the goal cap, not just pool availability ─────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_has_next_false_at_last_entry_within_goal(test_user):
    """
    With daily_goal=1 and spare reviewable PRs still in the pool, the only session entry must
    report has_next=False. Regression: has_next tracked pool availability and ignored the goal
    cap, so the Next button stayed enabled past the single dot.
    """
    req_a, ocdid_a = await _seed_open_pr("goal1a")
    req_b, ocdid_b = await _seed_open_pr("goal1b")
    try:
        session = await create_or_get_review_session(str(test_user), _STATE_CODE, daily_goal=1)
        result = await navigate_to_entry(session["id"], 1)
        assert result["total"] == 1, "a goal of 1 yields a single dot"
        assert result["has_next"] is False, "no next entry past the only slot in the session"
    finally:
        await _cleanup_open_pr(req_a, ocdid_a)
        await _cleanup_open_pr(req_b, ocdid_b)


# ── get_review_stats: available_count is per-user, not global ─────────────────

@pytest.mark.asyncio
@pytest.mark.integration
async def test_available_count_excludes_jurisdiction_claimed_by_another_user(test_user):
    """
    A jurisdiction another user's active session has already claimed must not
    count as "available" for this user — otherwise the landing page shows a
    review as available when clicking through would find nothing free.
    """
    from database.review_session_stats import get_review_stats

    changeset_id, ocdid = await _seed_open_pr("stats")
    provider_id = f"stats-other-{uuid.uuid4().hex[:8]}"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (provider, provider_user_id, email) VALUES ('test', %s, %s) RETURNING id",
            (provider_id, f"{provider_id}@test.com"),
        )
        row = await cur.fetchone()
        other_user = row[0]  # type: ignore[index]

    try:
        other_session = await _create_session(other_user)
        await _insert_entry(other_session, entry_number=1, status="claimed")
        async with pool.connection() as conn:
            await conn.execute(
                "UPDATE review_session_entries SET jurisdiction_ocdid = %s WHERE review_session_id = %s",
                (ocdid, other_session),
            )

        stats = await get_review_stats(str(test_user), _STATE_CODE)
        assert stats["available_count"] == 0, "Jurisdiction claimed by another user must not count as available"

        stats_for_claimer = await get_review_stats(str(other_user), _STATE_CODE)
        assert stats_for_claimer["available_count"] == 1, "The claiming user should still see their own claim as available"
    finally:
        async with pool.connection() as conn:
            await conn.execute(
                "DELETE FROM review_session_entries WHERE review_session_id IN (SELECT id FROM review_sessions WHERE user_id = %s)",
                (other_user,),
            )
            await conn.execute("DELETE FROM review_sessions WHERE user_id = %s", (other_user,))
            await conn.execute("DELETE FROM users WHERE provider = 'test' AND provider_user_id = %s", (provider_id,))
        await _cleanup_open_pr(changeset_id, ocdid)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_scrape_with_no_roster_never_reaches_the_pool():
    """Production carries 213 requests whose run succeeded but recorded no roster. Under a
    run-status test they become cards a reviewer opens and cannot publish — `_publish_roster`
    refuses, because publishing an empty roster would retire everyone in the jurisdiction.
    The pool tests the roster itself so it can never offer a card the publish path will reject."""
    ocdid = "ocd-jurisdiction/country:us/state:zz/place:pool_rosterless/government"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, status) VALUES (%s, 'active') ON CONFLICT DO NOTHING",
            (ocdid,),
        )
        await cur.execute(
            "INSERT INTO changesets (kind, jurisdiction_ocdid) "
            "VALUES ('scrape', %s) RETURNING id::text", (ocdid,)
        )
        changeset_id = (await cur.fetchone())[0]
        await cur.execute(
            "UPDATE changesets SET "
            "updated_at = CURRENT_TIMESTAMP WHERE id = %s", (changeset_id,)
        )

    rows, _, _ = await list_open_changesets(jurisdiction_ocdid=ocdid)
    assert changeset_id not in [r["changeset_id"] for r in rows]

    await _cleanup_open_pr(changeset_id, ocdid)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_dismissal_loses_the_race_to_a_reviewer_publishing():
    """Guarded in the statement, not by checking first: a reviewer may be publishing this very
    changeset, and a dismissal arriving mid-publish must not overwrite their decision."""
    ocdid = "ocd-jurisdiction/country:us/state:zz/place:pool_race/government"
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, status) VALUES (%s, 'active') "
            "ON CONFLICT DO NOTHING",
            (ocdid,),
        )
        await cur.execute(
            "INSERT INTO changesets (kind, jurisdiction_ocdid, published_at) "
            "VALUES ('scrape', %s, now()) RETURNING id::text",
            (ocdid,),
        )
        changeset_id = (await cur.fetchone())[0]
        await cur.execute(
            # The review pool is "this scrape saw somebody" — one sighting is a roster.
            "INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label, source_url) "
            "VALUES (%s, %s, 'Jane Doe', 'Mayor', 'https://zz.gov/council')",
            (changeset_id, ocdid),
        )

        assert await mark_dismissed(cur, [changeset_id], DismissalReason.SUPERSEDED) == []

        await cur.execute(
            "SELECT dismissed_at, dismissed_reason FROM changesets WHERE id::text = %s",
            (changeset_id,),
        )
        assert await cur.fetchone() == (None, None)
        await conn.rollback()
