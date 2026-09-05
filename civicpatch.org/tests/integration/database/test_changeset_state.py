"""The generated `changesets.changeset_state` column (migrations 164, renamed by 177).

Against the real DB because the thing under test is the CASE expression — Python cannot evaluate
it. What matters is that it agrees with `core.changeset_lifecycle.ChangesetState`, which is the
same fact written a second time in a second language.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio

import database.changeset_batches as batches_db
from core.changeset_lifecycle import INITIAL_STATE, ChangesetState
from database.changesets import (
    register_jurisdiction_edit_request,
    register_people_edit_request,
    register_sheet_import_request,
)
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from shared.utils.statuses import ChangesetKind
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_state/government"
_BATCH_LOCK_KEY = "zz_changeset_state"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM changeset_batches WHERE lock_key = %s", (_BATCH_LOCK_KEY,)
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
            RETURNING changeset_state
            """,
            (kind, _OCDID, published, dismissed, dismissed),
        )
        state = (await cur.fetchone())[0]
        await conn.commit()
    return state


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unresolved_changeset_is_open():
    """Three states, not five. RUNNING and FAILED described a *run*, and a changeset is only
    minted by one that succeeded — so every unresolved changeset has content to review,
    whatever produced it."""
    assert await _state_of("scrape", False, False) == ChangesetState.OPEN
    assert await _state_of("sheet_import", False, False) == ChangesetState.OPEN


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
        await cur.execute("SELECT DISTINCT changeset_state FROM changesets")
        seen = {row[0] for row in await cur.fetchall()}
    assert seen <= {s.value for s in ChangesetState}


async def _registered_state(changeset_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changeset_state FROM changesets WHERE id::text = %s", (changeset_id,)
        )
        return (await cur.fetchone())[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_every_kind_is_born_where_INITIAL_STATE_says():
    """`INITIAL_STATE` is the fifth copy of "born published": the other four are `published_at`
    in two INSERTs and its absence in the other two. Nothing read the map, so nothing forced
    them to agree. This is what makes it authoritative — change a register function without
    the map and this fails."""
    run_id = await factories.start_run(_OCDID)
    batch_id = await batches_db.start(
        batches_db.BatchKind.SHEET_IMPORT, _BATCH_LOCK_KEY, SYSTEM_USER_ID, {}
    )

    people_edit_id, import_id, jurisdiction_edit_id = (
        str(uuid.uuid4()),
        str(uuid.uuid4()),
        str(uuid.uuid4()),
    )
    await register_people_edit_request(people_edit_id, _OCDID, SYSTEM_USER_ID)
    await register_sheet_import_request(import_id, _OCDID, SYSTEM_USER_ID, batch_id)
    await register_jurisdiction_edit_request(
        jurisdiction_edit_id, _OCDID, "https://example.test/commit/1", SYSTEM_USER_ID
    )

    born = {
        ChangesetKind.SCRAPE: await _registered_state(
            await factories.complete_run(run_id)
        ),
        ChangesetKind.PEOPLE_EDIT: await _registered_state(people_edit_id),
        ChangesetKind.SHEET_IMPORT: await _registered_state(import_id),
        ChangesetKind.JURISDICTION_EDIT: await _registered_state(jurisdiction_edit_id),
    }

    assert born == {kind: state.value for kind, state in INITIAL_STATE.items()}
