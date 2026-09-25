"""Step 14: what `as_of` cuts, and what it never cuts.

Two claims the loader already makes and nothing pinned. `database/facts.py` states both in prose
--- "cutoff, withdraws never cut" and the records clause comparing `changesets.published_at` ---
so these exist to stop a later edit quietly reversing either.

The first is the one worth having: a rolled-back edit is gone from *every* as-of, including one
before the rollback was filed, because history is as currently believed rather than as once
printed (§17). Cut withdraws by date instead and a vandal's fact would reappear in any view old
enough to predate its removal.
"""

import datetime
import uuid

import pytest
import pytest_asyncio

from core.projection.live_facts import live_facts
from database import source_records
from database.database import get_pool
from database.facts import load_facts_for
from database.users import SYSTEM_USER_ID
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zm/place:asofville/government"
_PAGE = "https://asofville.example/council"
_T0 = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)
_LATER = _T0 + datetime.timedelta(days=60)
_BEFORE_LATER = _T0 + datetime.timedelta(days=1)
_AFTER_LATER = _T0 + datetime.timedelta(days=90)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM claims WHERE changeset_id IN "
            "  (SELECT id FROM changesets WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _organization() -> str:
    await factories.seed_jurisdiction(_OCDID, "zm", name="As Of Ville")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        await conn.commit()
    return organization_id


async def _scrape_published_later(organization_id: str, names: dict[str, str]) -> str:
    """A scrape whose records were written at `_T0` and published at `_LATER`.

    The two dates have to differ for the second test to say anything: `factories.published_scrape`
    sets created_at and published_at to the same instant, which cannot distinguish the cut.
    """
    changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets "
            "  (id, jurisdiction_ocdid, kind, created_at, updated_at, published_at) "
            "VALUES (%s, %s, 'scrape', %s, %s, %s)",
            (changeset_id, _OCDID, _T0, _T0, _LATER),
        )
        await conn.commit()
    await source_records.insert_source_records(
        changeset_id,
        _OCDID,
        {
            person_id: [
                {
                    "name": name,
                    "label": "Council Member",
                    "source_url": _PAGE,
                    "organization_id": organization_id,
                }
            ]
            for person_id, name in names.items()
        },
    )
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE source_records SET created_at = %s WHERE changeset_id = %s",
            (_T0, changeset_id),
        )
        await conn.commit()
    return changeset_id


async def _withdraw_of(record_id: str, changeset_id: str) -> str:
    withdraw_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO claims "
            "  (id, entity_type, entity_id, field_path, kind, value, sources, created_by, "
            "   created_at, changeset_id) "
            "VALUES (%s, 'source_record', %s, NULL, 'withdraw', 'null'::jsonb, "
            "        '[{\"note\": \"test\"}]'::jsonb, %s, %s, %s)",
            (withdraw_id, record_id, SYSTEM_USER_ID, _LATER, changeset_id),
        )
        await conn.commit()
    return withdraw_id


async def _rollback_changeset() -> str:
    changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets "
            "  (id, jurisdiction_ocdid, kind, created_at, updated_at, published_at) "
            "VALUES (%s, %s, 'rollback', %s, %s, %s)",
            (changeset_id, _OCDID, _LATER, _LATER, _LATER),
        )
        await conn.commit()
    return changeset_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_withdrawn_record_is_gone_from_an_as_of_before_the_withdraw():
    """The withdraw published two months after the as-of still removes its record.

    A withdraw is a correction, not an event: it says the fact never counted, so no view is old
    enough to still believe it. Cutting withdraws by date is what this pins against.
    """
    organization_id = await _organization()
    person_id = str(uuid.uuid4())
    await factories.published_source_record(
        _OCDID, organization_id, person_id, "Ada As-Of", "Mayor", _PAGE, _T0
    )

    facts = await load_facts_for(_OCDID, _BEFORE_LATER)
    [record] = facts.records
    await _withdraw_of(record.id, await _rollback_changeset())

    facts = await load_facts_for(_OCDID, _BEFORE_LATER)

    assert [w.entity_id for w in facts.withdraws] == [record.id]
    assert live_facts(facts).records == ()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_changesets_records_appear_together_when_it_published():
    """The cut is the changeset's `published_at`, not each record's `created_at`.

    Both records were written at `_T0` and published two months later, so an as-of between the
    two dates sees neither and one after sees both. A per-row cut would have leaked them early,
    one at a time.
    """
    organization_id = await _organization()
    first, second = str(uuid.uuid4()), str(uuid.uuid4())
    await _scrape_published_later(organization_id, {first: "Bo Early", second: "Cy Early"})

    before = await load_facts_for(_OCDID, _BEFORE_LATER)
    after = await load_facts_for(_OCDID, _AFTER_LATER)

    assert before.records == ()
    assert sorted(record.name for record in after.records) == ["Bo Early", "Cy Early"]
