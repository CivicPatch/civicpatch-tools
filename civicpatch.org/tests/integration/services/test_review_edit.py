"""A review pass is its own changeset, parented to the scrape it corrects (plan step 9f).

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio

from database import dismissals, organizations
from database.database import get_pool
from database.publications import publish_changeset
from database.source_records import insert_source_records
from database.users import SYSTEM_USER_ID
from schemas.jurisdictions import PersonEdit
from services import rollback
from services.jurisdiction_edits import edit_in_review
from shared.utils.statuses import DismissalReason
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_review_edit/government"
_SECOND_EMAIL = "second-reviewer@zz-review-edit.test"
_PAGE = "https://zz-review-edit.gov/council"
_T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)


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
        await cur.execute("DELETE FROM users WHERE email = %s", (_SECOND_EMAIL,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _seed() -> tuple[str, str]:
    """A published scrape listing Ada, and an open one listing her again. Returns (person, open)."""
    await factories.seed_jurisdiction(_OCDID, "zz", name="Review Edit Ville")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await conn.commit()
    person_id = str(uuid.uuid4())
    record = {"name": "Ada", "label": "Mayor", "source_url": _PAGE, "organization_id": organization_id}
    await factories.published_scrape(_OCDID, _T0, {person_id: [record]})
    await _publish(await _latest_published())

    scrape_id = str(uuid.uuid4())
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (id, kind, jurisdiction_ocdid, created_at, updated_at) "
            "VALUES (%s, 'scrape', %s, %s, %s)",
            (scrape_id, _OCDID, _T0 + timedelta(days=1), _T0 + timedelta(days=1)),
        )
        await conn.commit()
    await insert_source_records(scrape_id, _OCDID, {person_id: [record]})
    return person_id, scrape_id


async def _latest_published() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s "
            "AND published_at IS NOT NULL ORDER BY published_at DESC LIMIT 1",
            (_OCDID,),
        )
        row = await cur.fetchone()
        assert row is not None
        return row[0]


async def _publish(changeset_id: str) -> None:
    await publish_changeset(changeset_id, _OCDID, SYSTEM_USER_ID)


async def _rename(
    person_id: str, scrape_id: str, name: str, user_id: str = SYSTEM_USER_ID
) -> str:
    return await edit_in_review(
        _OCDID, [PersonEdit(id=person_id, fields={"name": name})], user_id, scrape_id
    )


async def _second_reviewer() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'github', %s, 'second-reviewer', 'default') RETURNING id::text",
            (_SECOND_EMAIL, _SECOND_EMAIL),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    return row[0]


async def _live_name(person_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name FROM people WHERE id::text = %s", (person_id,))
        row = await cur.fetchone()
        assert row is not None
        return row[0]


async def _state(changeset_id: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changeset_state FROM changesets WHERE id::text = %s", (changeset_id,)
        )
        row = await cur.fetchone()
        assert row is not None
        return row[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_saving_twice_files_under_one_edit_parented_to_the_scrape():
    person_id, scrape_id = await _seed()

    first = await _rename(person_id, scrape_id, "Ada M.")
    second = await _rename(person_id, scrape_id, "Ada M. Chen")

    assert first == second
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT kind, changeset_state, parent_changeset_id::text FROM changesets "
            "WHERE id::text = %s",
            (first,),
        )
        assert await cur.fetchone() == ("people_edit", "open", scrape_id)
        await cur.execute(
            "SELECT count(*) FROM claims WHERE changeset_id::text = %s", (scrape_id,)
        )
        row = await cur.fetchone()
        assert row is not None and row[0] == 0, "nothing is filed under the scrape itself"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_second_person_on_the_same_review_gets_their_own_edit():
    """A shared link, or a card handed on after the idle timeout: each pass stays attributable."""
    person_id, scrape_id = await _seed()
    second_user = await _second_reviewer()

    first = await _rename(person_id, scrape_id, "Ada M.")
    second = await _rename(person_id, scrape_id, "Ada M. Chen", second_user)
    await _publish(scrape_id)

    assert first != second
    assert await _state(first) == "published" and await _state(second) == "published"
    assert await _live_name(person_id) == "Ada M. Chen", "the later correction wins"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_nothing_goes_live_until_the_scrape_publishes_and_then_both_do():
    person_id, scrape_id = await _seed()
    edit_id = await _rename(person_id, scrape_id, "Ada M.")

    assert await _live_name(person_id) == "Ada"

    await _publish(scrape_id)

    assert await _live_name(person_id) == "Ada M."
    assert await _state(edit_id) == "published"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_dismissing_the_scrape_dismisses_its_edit():
    person_id, scrape_id = await _seed()
    edit_id = await _rename(person_id, scrape_id, "Ada M.")

    await dismissals.dismiss_all([scrape_id], DismissalReason.REJECTED, SYSTEM_USER_ID)

    assert await _state(edit_id) == "dismissed"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rolling_back_the_review_leaves_the_scrape_live():
    """The granularity 9f exists for: undo the corrections, keep what the page said."""
    person_id, scrape_id = await _seed()
    edit_id = await _rename(person_id, scrape_id, "Ada M.")
    await _publish(scrape_id)

    await rollback.rollback_changeset(edit_id, SYSTEM_USER_ID, "wrong person")

    assert await _live_name(person_id) == "Ada"
    assert await _state(scrape_id) == "published"
