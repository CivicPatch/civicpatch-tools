"""What `load_facts` hands the fold: membership claims found by their hashed id.

A membership claim names `membership_id(person, post)`, which nothing can read back, so the
loader finds it by computing the hash over the jurisdiction's people and posts. These pin that
it finds a claim on its own jurisdiction's membership, and not one on another's.
"""

import datetime
import uuid

import pytest
import pytest_asyncio

from core.projection.facts import EntityType
from core.projection.posts import PostKey
from database import divisions, posts
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


async def _label_claim(entity_id: str, label: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO assertions "
            "  (entity_type, entity_id, field_path, kind, value, created_by, created_at) "
            "VALUES ('membership', %s, 'label', 'accept', to_jsonb(%s::text), %s, %s)",
            (entity_id, label, SYSTEM_USER_ID, _T0),
        )
        await conn.commit()


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
    await _label_claim(membership_id(person_id, post_id), "zl-Mayor (interim)")

    facts = await load_facts_for(_OCDID, datetime.datetime.now(datetime.timezone.utc))

    membership_claims = [c for c in facts.claims if c.entity_type == EntityType.MEMBERSHIP]
    assert [(c.field_path, c.value) for c in membership_claims] == [
        ("label", "zl-Mayor (interim)")
    ]


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
    elsewhere = PostKey(
        organization_id=other_organization, role_id="mayor", division_ocdid=_BASE
    ).post_id
    await _label_claim(membership_id(person_id, elsewhere), "zl-Elsewhere")

    facts = await load_facts_for(_OCDID, datetime.datetime.now(datetime.timezone.utc))

    assert [c for c in facts.claims if c.entity_type == EntityType.MEMBERSHIP] == []
