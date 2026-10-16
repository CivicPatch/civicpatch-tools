"""Opening a jurisdiction pull request against real rows: the jurisdiction and its changesets.
Only GitHub is mocked."""

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from database.database import get_pool
from database.users import SYSTEM_USER_ID
from lib.github.api import PullRequestState
from services.jurisdiction_pull_request import (
    JurisdictionEdit,
    PullRequestAlreadyOpen,
    UnknownJurisdiction,
    open_jurisdiction_pull_request,
    fetch_pull_request_outcomes,
)
from shared.utils.statuses import PullRequestLabel

_CITY = "ocd-jurisdiction/country:us/state:wa/place:zyprcity/government"


async def _execute(sql, params=()):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def _rows():
    await _execute(
        """
        INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
        VALUES (%s, 'wa', %s::jsonb, now()) ON CONFLICT (jurisdiction_ocdid) DO NOTHING
        """,
        (_CITY, json.dumps({"name": "Zyprcity city"})),
    )
    yield
    await _execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_CITY,))
    await _execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_CITY,))


def _github_opens(number: int):
    return patch(
        "services.jurisdiction_pull_request._open_pr",
        new_callable=AsyncMock,
        return_value=(number, f"https://example.test/pull/{number}"),
    )


async def _open(url: str = "https://zyprcity.gov", ocdid: str = _CITY):
    edit = JurisdictionEdit(patch={"url": url}, sources=["https://example.test"])
    return await open_jurisdiction_pull_request(ocdid, edit, PullRequestLabel.SYSTEM, SYSTEM_USER_ID)


async def _open_changesets() -> list[tuple[str, str]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT change_url, created_by_user_id::text FROM changesets
            WHERE jurisdiction_ocdid = %s AND published_at IS NULL AND dismissed_at IS NULL
            """,
            (_CITY,),
        )
        return list(await cur.fetchall())


async def _dismissed_reasons() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT dismissed_reason FROM changesets WHERE jurisdiction_ocdid = %s AND dismissed_at IS NOT NULL",
            (_CITY,),
        )
        return [row[0] for row in await cur.fetchall()]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_pull_request_is_tracked_as_an_open_changeset_by_its_author():
    with _github_opens(7) as mock_github:
        opened = await _open()

    assert opened.pull_request_number == 7
    assert await _open_changesets() == [("https://example.test/pull/7", SYSTEM_USER_ID)]
    author = mock_github.call_args.args[3]
    assert author.name == "CivicPatch"


def _first_one_is(state: PullRequestState):
    return patch(
        "services.jurisdiction_pull_request._pull_request_state",
        new_callable=AsyncMock,
        return_value=state,
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("state", [PullRequestState.OPEN, PullRequestState.MERGED])
async def test_a_second_pull_request_waits_while_the_first_is_open_or_merged(state):
    """Merged but not synced in yet still waits: the sync publishes it."""
    with _github_opens(7):
        await _open()

    with _first_one_is(state), _github_opens(8) as mock_github, pytest.raises(PullRequestAlreadyOpen, match="pull/7"):
        await _open("https://zyprcity.gov/new")
    mock_github.assert_not_called()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_closed_pull_request_is_rejected_and_a_new_one_opens():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.CLOSED), _github_opens(8):
        opened = await _open("https://zyprcity.gov/new")

    assert opened.pull_request_number == 8
    assert await _open_changesets() == [("https://example.test/pull/8", SYSTEM_USER_ID)]
    assert await _dismissed_reasons() == ["rejected"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_jurisdiction_is_refused():
    missing = "ocd-jurisdiction/country:us/state:wa/place:zyprmissing/government"

    with _github_opens(7), pytest.raises(UnknownJurisdiction):
        await _open(ocdid=missing)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_settling_after_a_sync_publishes_a_merged_pull_request():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.MERGED):
        await fetch_pull_request_outcomes()

    assert await _open_changesets() == []
    assert await _dismissed_reasons() == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_settling_after_a_sync_rejects_a_closed_pull_request():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.CLOSED):
        await fetch_pull_request_outcomes()

    assert await _dismissed_reasons() == ["rejected"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_settling_leaves_an_open_pull_request_waiting():
    with _github_opens(7):
        await _open()

    with _first_one_is(PullRequestState.OPEN):
        await fetch_pull_request_outcomes()

    assert await _open_changesets() == [("https://example.test/pull/7", SYSTEM_USER_ID)]
