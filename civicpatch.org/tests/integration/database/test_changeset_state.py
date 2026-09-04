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


async def _state_of(kind: str, status: str | None, published: bool, dismissed: bool) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO changesets (kind, status, jurisdiction_ocdid, arguments_json,
                                    published_at, dismissed_at, dismissed_reason)
            VALUES (%s, %s, %s, '{}'::jsonb,
                    CASE WHEN %s THEN now() END,
                    CASE WHEN %s THEN now() END,
                    CASE WHEN %s THEN 'rejected' END)
            RETURNING state
            """,
            (kind, status, _OCDID, published, dismissed, dismissed),
        )
        state = (await cur.fetchone())[0]
        await conn.commit()
    return state


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_scrape_mid_run_is_running():
    """`status` carries step names as well as outcomes — `SCRAPE_PAGE` is where the run is, not
    how it ended, so anything non-terminal is progress."""
    assert await _state_of("scrape", "SCRAPE_PAGE", False, False) == ChangesetState.RUNNING


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_finished_scrape_is_ready():
    assert await _state_of("scrape", "SUCCESS", False, False) == ChangesetState.READY


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_that_produced_nothing_is_failed():
    for status in ("ERROR", "CANCELLED"):
        assert await _state_of("scrape", status, False, False) == ChangesetState.FAILED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_changeset_with_no_run_is_ready():
    """An import and a jurisdiction edit have no run to wait for — `changesets_scrape_has_a_run`
    forces `status IS NULL` for anything that is not a scrape."""
    assert await _state_of("sheet_import", None, False, False) == ChangesetState.READY


@pytest.mark.asyncio
@pytest.mark.integration
async def test_publishing_wins_over_the_run():
    """A changeset that published is published whatever its run says afterwards. Ordering in
    the CASE is the definition, not an accident of how it was written."""
    assert await _state_of("scrape", "ERROR", True, False) == ChangesetState.PUBLISHED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dismissing_wins_over_the_run():
    assert await _state_of("scrape", "SUCCESS", False, True) == ChangesetState.DISMISSED


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_column_never_says_anything_the_enum_does_not():
    """Two definitions of one fact, in two languages. A value here that `ChangesetState` does
    not carry means the Python side cannot reason about rows the database produces."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT DISTINCT state FROM changesets")
        stored = {row[0] for row in await cur.fetchall()}
    assert stored <= {state.value for state in ChangesetState}
