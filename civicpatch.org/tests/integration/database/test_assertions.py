"""Integration tests for `assertions` — what a human said about a row.

Against the real DB because the guarantees under test are constraints and derivation, not
Python: the CHECKs, `UNIQUE NULLS NOT DISTINCT`, and `DISTINCT ON` picking the latest.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import json
import uuid

import pytest
import pytest_asyncio
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation

from database import assertions, divisions, organizations, posts
from database.database import get_pool
from schemas.assertions import Assertion, AssertionKind, EntityType, Source

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_assert/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_assert"
_USER = "zz-assert-user@example.com"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM assertions WHERE asserted_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_USER,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_USER,))
        for table in ("posts", "divisions", "organizations"):
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
    yield
    await _wipe()


async def _seed() -> tuple[str, str]:
    """A user to assert, and a post to assert about."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'email', %s, 'admins') RETURNING id::text",
            (_USER, _USER),
        )
        user_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)
        await conn.commit()
    return user_id, post_id


def _confirm(post_id: str, **overrides) -> Assertion:
    return Assertion(
        entity_type=EntityType.POST,
        entity_id=post_id,
        kind=AssertionKind.CONFIRM,
        sources=[Source(note="phoned the clerk, there really are five trustees")],
        **overrides,
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_confirming_a_post_verifies_it_without_a_publish():
    """The case that could not be done any other way. A transient's request was superseded, so
    publishing it is refused by the guard — the rows most needing human judgement were
    permanently locked out of receiving it."""
    user_id, post_id = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts.list_for_jurisdiction(cur, _OCDID)
        assert rows[0]["verified"] is False

    await assertions.create(_confirm(post_id), user_id)

    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts.list_for_jurisdiction(cur, _OCDID)
    assert rows[0]["verified"] is True
    assert rows[0]["holders"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_evidence_survives():
    """`sources` is the reason this could not be a `verified_at` column. "Phoned the clerk"
    exists nowhere else — it came from outside a publish."""
    user_id, post_id = await _seed()
    await assertions.create(_confirm(post_id), user_id)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await assertions.list_for_entity(cur, EntityType.POST, post_id)

    assert len(rows) == 1
    assert rows[0]["sources"][0]["note"].startswith("phoned the clerk")
    assert rows[0]["asserted_by_name"] == _USER


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_later_assertion_supersedes_without_erasing():
    """Append-only. Correcting twice leaves both rows, and the current value is the latest —
    which is what makes "what did we believe then" answerable at all."""
    user_id, _ = await _seed()
    person_id = str(uuid.uuid4())

    for value in ("first@town.gov", "second@town.gov"):
        await assertions.create(
            Assertion(
                entity_type=EntityType.PERSON,
                entity_id=person_id,
                field_path="email",
                kind=AssertionKind.CORRECT,
                value=value,
            ),
            user_id,
        )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        current = await assertions.current_corrections(cur, EntityType.PERSON, person_id)
        rows = await assertions.list_for_entity(cur, EntityType.PERSON, person_id)

    assert current == {"email": "second@town.gov"}
    assert len(rows) == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_retraction_removes_the_correction_but_not_its_record():
    """Retracting is a row, never a delete — otherwise "we were wrong" and "we never said it"
    become indistinguishable."""
    user_id, _ = await _seed()
    person_id = str(uuid.uuid4())

    await assertions.create(
        Assertion(
            entity_type=EntityType.PERSON,
            entity_id=person_id,
            field_path="email",
            kind=AssertionKind.CORRECT,
            value="wrong@town.gov",
        ),
        user_id,
    )
    await assertions.create(
        Assertion(
            entity_type=EntityType.PERSON,
            entity_id=person_id,
            field_path="email",
            kind=AssertionKind.RETRACT,
        ),
        user_id,
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        current = await assertions.current_corrections(cur, EntityType.PERSON, person_id)
        rows = await assertions.list_for_entity(cur, EntityType.PERSON, person_id)

    assert current == {}
    assert [row["kind"] for row in rows] == ["retract", "correct"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_assertion_nobody_made_is_refused():
    """`asserted_by` is NOT NULL, unlike `requests.resolved_by_user_id` where NULL means a
    machine gave up. Nothing machine-generated belongs in here."""
    _, post_id = await _seed()

    with pytest.raises(ForeignKeyViolation):
        await assertions.create(_confirm(post_id), str(uuid.uuid4()))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_entity_type_is_refused():
    """A CHECK rather than free text: `entity_type` is joined against by every reader, and a
    typo would silently make an assertion invisible instead of failing."""
    user_id, post_id = await _seed()

    pool = await get_pool()
    with pytest.raises(CheckViolation):
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO assertions (entity_type, entity_id, kind, asserted_by) "
                "VALUES ('organisation', %s, 'confirm', %s)",
                (post_id, user_id),
            )
            await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_whole_entity_assertion_cannot_be_filed_twice_identically():
    """`field_path` is NULL for a whole-entity assertion, and Postgres treats NULLs as distinct
    in a unique constraint by default — so without `NULLS NOT DISTINCT` the guard against exact
    duplicates would silently not apply to precisely the entity-level case."""
    user_id, post_id = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO assertions (entity_type, entity_id, kind, asserted_by, asserted_at) "
            "VALUES ('post', %s, 'confirm', %s, '2026-08-20T00:00:00Z')",
            (post_id, user_id),
        )
        await conn.commit()

    with pytest.raises(UniqueViolation):
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO assertions (entity_type, entity_id, kind, asserted_by, asserted_at) "
                "VALUES ('post', %s, 'confirm', %s, '2026-08-20T00:00:00Z')",
                (post_id, user_id),
            )
            await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_post_someone_vouched_for_cannot_be_deleted():
    """`assertions` has no foreign key — the price of an event log over heterogeneous subjects
    — so nothing refuses the delete on its behalf. Orphaning would also discard the only copy
    of *why* someone vouched: "phoned the clerk" exists nowhere else."""
    user_id, post_id = await _seed()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert await posts.delete_if_unheld(cur, post_id) is True
        await conn.rollback()

    await assertions.create(_confirm(post_id), user_id)

    async with pool.connection() as conn, conn.cursor() as cur:
        assert await posts.delete_if_unheld(cur, post_id) is False
