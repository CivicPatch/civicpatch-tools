"""One membership row per period held, through the real loader, writer and rollback (step 15).

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from database import projection as projection_db
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.jurisdictions import PersonEdit
from services import rollback
from services.jurisdiction_edits import edit_published_roster
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_history/government"
_PAGE = "https://zz-history.gov/council"
_T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(days=30)
_T2 = _T0 + timedelta(days=60)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM claims WHERE changeset_id IN "
            "(SELECT id FROM changesets WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "changesets", "organizations", "people"):
            await cur.execute(f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _council() -> str:
    await factories.seed_jurisdiction(_OCDID, "zz", name="History Ville")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        council = await factories.default_organization(cur, _OCDID)
        await conn.commit()
    return council


async def _scrape(at: datetime, jane: str, label: str, council: str) -> None:
    """Rebuilt directly: `publish_changeset` would refuse a backdated scrape after an edit."""
    record = {"name": "Jane Doe", "label": label, "source_url": _PAGE, "organization_id": council}
    await factories.published_scrape(_OCDID, at, {jane: [record]})
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await projection_db.rebuild_from_facts(cur, _OCDID)
        await conn.commit()


async def _periods(person_id: str) -> list[tuple[str, datetime, datetime | None]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT p.role_id, m.opened_at, m.closed_at FROM memberships m "
            "JOIN posts p ON p.id = m.post_id WHERE m.person_id = %s ORDER BY m.opened_at",
            (person_id,),
        )
        return list(await cur.fetchall())


@pytest.mark.asyncio
@pytest.mark.integration
async def test_jane_mayor_then_member_then_mayor_is_three_rows():
    council = await _council()
    jane = str(uuid.uuid4())

    await _scrape(_T0, jane, "Mayor", council)
    await _scrape(_T1, jane, "Council Member", council)
    await _scrape(_T2, jane, "Mayor", council)

    assert await _periods(jane) == [
        ("mayor", _T0, _T1),
        ("council-member", _T1, _T2),
        ("mayor", _T2, None),
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rolling_back_a_reject_removes_the_boundary_it_made():
    """History never shows what was rolled back: her one period runs on unbroken."""
    council = await _council()
    jane = str(uuid.uuid4())
    await _scrape(_T0, jane, "Mayor", council)

    reject = await edit_published_roster(_OCDID, [PersonEdit(id=jane, offices=[])], SYSTEM_USER_ID)
    [(_, _, closed_at)] = await _periods(jane)
    assert closed_at is not None

    await rollback.rollback_changeset(reject, SYSTEM_USER_ID, "she is still mayor")

    assert await _periods(jane) == [("mayor", _T0, None)]


async def _start_date(person_id: str) -> str | None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT start_date FROM memberships WHERE person_id = %s AND closed_at IS NULL",
            (person_id,),
        )
        row = await cur.fetchone()
        assert row is not None
        return row[0]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.xfail(
    strict=True,
    reason="known bug: the editor files dates as person claims, the fold reads membership claims",
)
async def test_a_start_date_saved_in_the_editor_reaches_the_membership():
    council = await _council()
    jane = str(uuid.uuid4())
    await _scrape(_T0, jane, "Mayor", council)

    await edit_published_roster(
        _OCDID, [PersonEdit(id=jane, fields={"start_date": "2024-01-01"})], SYSTEM_USER_ID
    )

    assert await _start_date(jane) == "2024-01-01"
