"""`name_for` — the entity's name, looked up when a change log is written.

Against the real DB because it is three SQL statements, one per entity type, each joining
somewhere different.

It used to run on every history page load: an assertion payload carried only ids, so the reader
resolved a name per row (deduped, because accepting four fields on one person writes four rows).
`Change.subject` stores it at write time instead, which is also the only way to answer once the
entity has been deleted — and that is what this has to keep doing correctly, silently falling
back to the entity type if it ever stops.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio

from database.database import get_pool
from database.entity_jurisdiction import name_for
from schemas.assertions import EntityType

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_names/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,)
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


async def _person(name: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        person_id = str(uuid.uuid4())
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id, _OCDID, name),
        )
        await conn.commit()
    return person_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_person_is_named():
    person_id = await _person("Ada Lovelace")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await name_for(cur, EntityType.PERSON, person_id) == "Ada Lovelace"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_entity_that_is_gone_has_no_name():
    """The caller writes the entity type instead. Silently returning None for a *live* entity
    would look identical, which is why this is worth pinning."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await name_for(cur, EntityType.PERSON, str(uuid.uuid4())) is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_membership_is_named_by_who_holds_it():
    """A seat has no name of its own — it is read as the person in it."""
    from core.post_derivation import DerivedMembership
    from database import divisions, memberships, organizations, posts

    person_id = await _person("Ada Lovelace")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        org = await organizations.find_or_create(cur, _OCDID)
        base = "ocd-division/country:us/state:zz/place:zz_names"
        await divisions.find_or_create(cur, base, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, org, "mayor", base)
        membership_id = await memberships.upsert(
            cur, DerivedMembership(person_id=person_id), post_id, org, "2026-01-01"
        )
        await conn.commit()

        assert await name_for(cur, EntityType.MEMBERSHIP, membership_id) == "Ada Lovelace"
        assert await name_for(cur, EntityType.POST, post_id) == "Mayor"
