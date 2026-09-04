"""The generated `changesets.state` column (migration 164).

Against the real DB because the thing under test is the CASE expression — Python cannot evaluate
it. What matters is that it agrees with `core.changeset_lifecycle.ChangesetState`, which is the
same fact written a second time in a second language.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from core.changeset_lifecycle import ChangesetState
from database.database import get_pool

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_state/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await conn.commit()
    yield
    await _wipe()


async def _state_of(kind: str, published: bool, dismissed: bool) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO changesets
                (kind, jurisdiction_ocdid, published_at, dismissed_at, dismissed_reason)
            VALUES (%s, %s, CASE WHEN %s THEN now() END, CASE WHEN %s THEN now() END,
                    CASE WHEN %s THEN 'rejected' END)
            RETURNING state
            """,
            (kind, _OCDID, published, dismissed, dismissed),
        )
        state = (await cur.fetchone())[0]
        await conn.commit()
    return state


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unresolved_changeset_is_ready():
    """Three states, not five. RUNNING and FAILED described a *run*, and a changeset is only
    minted by one that succeeded — so every unresolved changeset has content to review,
    whatever produced it."""
    assert await _state_of("scrape", False, False) == ChangesetState.READY
    assert await _state_of("sheet_import", False, False) == ChangesetState.READY


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publishing_and_dismissing_are_terminal():
    assert await _state_of("scrape", True, False) == ChangesetState.PUBLISHED
    assert await _state_of("scrape", False, True) == ChangesetState.DISMISSED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_column_never_says_anything_the_enum_does_not():
    """The generated column and `ChangesetState` are two copies of one fact."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT DISTINCT state FROM changesets")
        seen = {row[0] for row in await cur.fetchall()}
    assert seen <= {s.value for s in ChangesetState}
