import pytest
from collections import namedtuple
from unittest.mock import AsyncMock

from database.review_session_navigation import _navigate_to_existing_entry

SESSION_ID = "session-456"
STATE_CODE = "tx"
JURIS_A = "ocd-jurisdiction/country:us/state:tx/place:a"
JURIS_B = "ocd-jurisdiction/country:us/state:tx/place:b"


def _entry_row(jurisdiction_ocdid):
    Row = namedtuple("Row", ["id", "changeset_ids", "jurisdiction_ocdid"])
    return Row(id=1, changeset_ids=["req-1"], jurisdiction_ocdid=jurisdiction_ocdid)


def _cursor(fetchone=(), fetchall=()):
    cur = AsyncMock()
    cur.execute = AsyncMock()
    cur.fetchone = AsyncMock(side_effect=list(fetchone))
    cur.fetchall = AsyncMock(side_effect=list(fetchall))
    return cur


# ── _navigate_to_existing_entry: has_next peek excludes in-progress ────────────


@pytest.mark.asyncio
@pytest.mark.unit
async def test_has_next_false_when_only_in_progress_jurisdictions_remain():
    # Bug #2: session has A and B claimed; user resumes at entry B (entry 2);
    # there is no entry 3; the only PR the peek would otherwise find is A, but A
    # is already claimed. has_next must be False.
    cur = _cursor(
        fetchone=[_entry_row(JURIS_B), None],
        fetchall=[[(JURIS_A,), (JURIS_B,)], []],
    )

    result = await _navigate_to_existing_entry(cur, SESSION_ID, 2, STATE_CODE)

    assert result is not None
    _, _, has_next = result
    assert has_next is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_has_next_peek_excludes_in_progress():
    # The peek's exclusion list is the session's in-progress (claimed) changeset_ids.
    # Resolved/published PRs are already filtered out by AVAILABLE_FOR_REVIEW upstream.
    cur = _cursor(
        fetchone=[_entry_row(JURIS_B), None],
        fetchall=[[(JURIS_A,), (JURIS_B,)], []],
    )

    await _navigate_to_existing_entry(cur, SESSION_ID, 2, STATE_CODE)

    # Call order: existing-entry SELECT, next-entry SELECT, in-progress SELECT,
    # then _allocate_next_review's SELECT — index 3.
    peek_params = cur.execute.call_args_list[3].args[1]
    excluded = peek_params[1]

    assert {JURIS_A, JURIS_B} <= set(excluded)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_has_next_true_short_circuits_when_next_entry_claimed():
    # When entry n+1 already exists with status='claimed', has_next is True
    # without invoking the peek path.
    cur = _cursor(fetchone=[_entry_row(JURIS_A), (1,)])

    result = await _navigate_to_existing_entry(cur, SESSION_ID, 1, STATE_CODE)

    assert result is not None
    _, _, has_next = result
    assert has_next is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_returns_none_when_entry_does_not_exist():
    cur = _cursor(fetchone=[None])

    result = await _navigate_to_existing_entry(cur, SESSION_ID, 99, STATE_CODE)

    assert result is None
