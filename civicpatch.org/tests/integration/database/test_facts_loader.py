"""What `load_facts` hands the fold: one jurisdiction's facts, and whose.

A membership claim names `membership_id(person, post)`, which nothing can read back and no
query can join on, so the loader scopes them by the changeset they were made under. These pin
that a claim made here is loaded, that one made in another jurisdiction is not, and that one
made under no changeset at all still reaches the fold.

The last two pin `including`: the one unpublished changeset a caller asks to see as though it
had published, which is what a proposed roster is (R3).
"""

import datetime
import uuid

import pytest
import pytest_asyncio

from core.projection.facts import EntityType, PostKey
from database import divisions, posts, source_records
from database.database import get_pool
from database.facts import load_facts_for
from database.users import SYSTEM_USER_ID
from shared.utils.membership_ids import membership_id
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zl/place:loadville/government"
_OTHER = "ocd-jurisdiction/country:us/state:zl/place:elsewhere/government"
_BASE = "ocd-division/country:us/state:zl/place:loadville"
_PAGE = "https://loadville.example/council"
_T0 = datetime.datetime(2026, 3, 1, tzinfo=datetime.timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM assertions WHERE entity_type = 'membership' AND created_by = %s "
            "AND value::text LIKE %s",
            (SYSTEM_USER_ID, '%"zl-%'),
        )
        await cur.execute(
            "DELETE FROM assertions WHERE kind = 'withdraw' AND created_by = %s",
            (SYSTEM_USER_ID,),
        )
        for ocdid in (_OCDID, _OTHER):
            await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (ocdid,))
            await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean():
    await _wipe()
    yield
    await _wipe()


async def _changeset_of(jurisdiction_ocdid: str) -> str:
    """A published changeset of this jurisdiction: what a claim is made under, and what scopes
    it to one jurisdiction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s "
            "AND published_at IS NOT NULL ORDER BY published_at LIMIT 1",
            (jurisdiction_ocdid,),
        )
        row = await cur.fetchone()
        assert row is not None, "the fixture publishes one"
        return row[0]


async def _label_claim(entity_id: str, label: str, changeset_id: str | None = None) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO assertions "
            "  (entity_type, entity_id, field_path, kind, value, sources, created_by, "
            "   created_at, changeset_id) "
            "VALUES ('membership', %s, 'label', 'accept', to_jsonb(%s::text), "
            "        '[{\"note\": \"test\"}]'::jsonb, %s, %s, %s)",
            (entity_id, label, SYSTEM_USER_ID, _T0, changeset_id),
        )
        await conn.commit()


async def _withdraw(fact_id: str, changeset_id: str) -> str:
    """A withdraw naming a fact. `entity_id` is arbitrary: the loader scopes by the changeset,
    not by what the withdraw names."""
    withdraw_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO assertions "
            "  (id, entity_type, entity_id, field_path, kind, value, sources, created_by, "
            "   created_at, changeset_id) "
            "VALUES (%s, 'claim', %s, NULL, 'withdraw', 'null'::jsonb, "
            "        '[{\"note\": \"test\"}]'::jsonb, %s, %s, %s)",
            (withdraw_id, fact_id, SYSTEM_USER_ID, _T0, changeset_id),
        )
        await conn.commit()
    return withdraw_id


def _labels_of(facts, entity_id: str) -> list:
    return [
        claim.value
        for claim in facts.claims
        if claim.entity_type == EntityType.MEMBERSHIP and claim.entity_id == entity_id
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_claim_on_this_jurisdictions_membership_is_loaded():
    person_id = str(uuid.uuid4())
    await factories.seed_jurisdiction(_OCDID, "zl")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)
        await conn.commit()
    await factories.published_source_record(
        _OCDID, organization_id, person_id, "Lia Load", "Mayor", _PAGE, _T0
    )
    post_id = PostKey(
        organization_id=organization_id, role_id="mayor", division_ocdid=_BASE
    ).post_id
    entity_id = membership_id(person_id, post_id)
    await _label_claim(entity_id, "zl-Mayor (interim)", await _changeset_of(_OCDID))

    facts = await load_facts_for(_OCDID, datetime.datetime.now(datetime.timezone.utc))

    assert _labels_of(facts, entity_id) == ["zl-Mayor (interim)"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_claim_on_another_jurisdictions_membership_is_not():
    person_id = str(uuid.uuid4())
    await factories.seed_jurisdiction(_OCDID, "zl")
    await factories.seed_jurisdiction(_OTHER, "zl", name="Elsewhere")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        other_organization = await factories.default_organization(cur, _OTHER)
        await conn.commit()
    await factories.published_source_record(
        _OCDID, organization_id, person_id, "Lia Load", "Mayor", _PAGE, _T0
    )
    await factories.published_source_record(
        _OTHER, other_organization, str(uuid.uuid4()), "Bo Else", "Mayor", _PAGE, _T0
    )
    elsewhere = PostKey(
        organization_id=other_organization, role_id="mayor", division_ocdid=_BASE
    ).post_id
    entity_id = membership_id(person_id, elsewhere)
    await _label_claim(entity_id, "zl-Elsewhere", await _changeset_of(_OTHER))

    facts = await load_facts_for(_OCDID, datetime.datetime.now(datetime.timezone.utc))

    assert _labels_of(facts, entity_id) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_claim_made_under_no_changeset_is_loaded():
    """Why the scope has an `OR`: a label set outside a review names no jurisdiction, and it
    still has to reach the fold. The fold matches it to its own memberships, so one about
    somebody else's is inert rather than wrong."""
    person_id = str(uuid.uuid4())
    await factories.seed_jurisdiction(_OCDID, "zl")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        await conn.commit()
    await factories.published_source_record(
        _OCDID, organization_id, person_id, "Lia Load", "Mayor", _PAGE, _T0
    )
    post_id = PostKey(
        organization_id=organization_id, role_id="mayor", division_ocdid=_BASE
    ).post_id
    entity_id = membership_id(person_id, post_id)
    await _label_claim(entity_id, "zl-Mayor (unattributed)")

    facts = await load_facts_for(_OCDID, datetime.datetime.now(datetime.timezone.utc))

    assert _labels_of(facts, entity_id) == ["zl-Mayor (unattributed)"]


async def _unpublished_scrape(person_id: str, organization_id: str, label: str) -> str:
    """A scrape nobody has approved: its records are stored, and no roster derives them."""
    changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (id, jurisdiction_ocdid, kind) VALUES (%s, %s, 'scrape')",
            (changeset_id, _OCDID),
        )
        await conn.commit()
    await source_records.insert_source_records(
        changeset_id,
        _OCDID,
        {
            person_id: [
                {
                    "name": "Lia Load",
                    "label": label,
                    "source_url": _PAGE,
                    "organization_id": organization_id,
                }
            ]
        },
    )
    return changeset_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unpublished_changeset_is_not_in_the_live_roster():
    person_id = str(uuid.uuid4())
    await factories.seed_jurisdiction(_OCDID, "zl")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        await conn.commit()
    await factories.published_source_record(
        _OCDID, organization_id, person_id, "Lia Load", "Mayor", _PAGE, _T0
    )
    await _unpublished_scrape(person_id, organization_id, "Clerk")

    facts = await load_facts_for(_OCDID, datetime.datetime.now(datetime.timezone.utc))

    assert sorted(record.label for record in facts.records) == ["Mayor"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_including_one_changeset_reads_it_as_though_it_had_published():
    """A proposed roster is `derive(published facts + this changeset)`. Nothing is written,
    and the changeset stays unpublished."""
    person_id = str(uuid.uuid4())
    await factories.seed_jurisdiction(_OCDID, "zl")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        await conn.commit()
    await factories.published_source_record(
        _OCDID, organization_id, person_id, "Lia Load", "Mayor", _PAGE, _T0
    )
    proposed = await _unpublished_scrape(person_id, organization_id, "Clerk")

    facts = await load_facts_for(
        _OCDID, datetime.datetime.now(datetime.timezone.utc), including=proposed
    )

    assert sorted(record.label for record in facts.records) == ["Clerk", "Mayor"]
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT published_at FROM changesets WHERE id = %s", (proposed,))
        assert (await cur.fetchone())[0] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_withdraw_in_this_jurisdiction_is_loaded():
    person_id = str(uuid.uuid4())
    await factories.seed_jurisdiction(_OCDID, "zl")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        await conn.commit()
    await factories.published_source_record(
        _OCDID, organization_id, person_id, "Lia Load", "Mayor", _PAGE, _T0
    )
    mine = await _withdraw(str(uuid.uuid4()), await _changeset_of(_OCDID))

    facts = await load_facts_for(_OCDID, datetime.datetime.now(datetime.timezone.utc))

    assert mine in {withdraw.id for withdraw in facts.withdraws}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_withdraw_in_another_jurisdiction_is_not_loaded():
    """Scoped by the changeset's jurisdiction, not global: a fold here must not read every
    rollback in the system. A withdraw's changeset carries the scope of the fact it cancels,
    so one that could affect this jurisdiction is filed under it."""
    person_id = str(uuid.uuid4())
    await factories.seed_jurisdiction(_OCDID, "zl")
    await factories.seed_jurisdiction(_OTHER, "zl", name="Elsewhere")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await factories.default_organization(cur, _OCDID)
        other_organization = await factories.default_organization(cur, _OTHER)
        await conn.commit()
    await factories.published_source_record(
        _OCDID, organization_id, person_id, "Lia Load", "Mayor", _PAGE, _T0
    )
    await factories.published_source_record(
        _OTHER, other_organization, str(uuid.uuid4()), "Bo Else", "Mayor", _PAGE, _T0
    )
    elsewhere = await _withdraw(str(uuid.uuid4()), await _changeset_of(_OTHER))

    facts = await load_facts_for(_OCDID, datetime.datetime.now(datetime.timezone.utc))

    assert elsewhere not in {withdraw.id for withdraw in facts.withdraws}
