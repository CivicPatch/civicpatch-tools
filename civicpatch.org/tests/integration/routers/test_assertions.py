"""Route-level integration tests for the assertions endpoint.

TestClient against the real DB with auth mocked. The DB-layer tests cover the constraints and
the derivation; these cover what only crosses the wire — that the payload model accepts the
three kinds, and that an unattributable assertion is refused rather than stored.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import assertions, divisions, organizations, posts
from database.database import get_pool
from lib.auth import get_optional_user
from schemas.assertions import AssertionKind
from routers.api import assertions as assertions_router
from schemas.assertions import EntityType
from schemas.common import Identity

_PREFIX = "/api/v1/assertions"
_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_aroute/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_aroute"
_EMAIL = "zz-assert-route@example.com"

_USER_ID: str | None = None


def _identity() -> Identity:
    return Identity(
        type="session",
        provider="email",
        provider_user_id=_EMAIL,
        email=_EMAIL,
        role="admins",
        user_id=_USER_ID,
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(assertions_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: _identity()
    return TestClient(app)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM assertions WHERE asserted_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_EMAIL,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_EMAIL,))
        # Before organizations and jurisdictions: both are FKs from changesets.
        await cur.execute(
            "DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
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
    global _USER_ID
    await _wipe()
    yield
    _USER_ID = None
    await _wipe()


async def _seed() -> str:
    """A signed-in user and a post to assert about."""
    global _USER_ID
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'email', %s, 'admins') RETURNING id::text",
            (_EMAIL, _EMAIL),
        )
        _USER_ID = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)
        await conn.commit()
    return post_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_vouching_for_a_post_makes_it_read_verified(client):
    """The whole point of the endpoint: a curator vouches for an office nobody has published,
    and the roster says so. Previously only a publish could make this true.

    An ordinary field assertion since 137 — "there really are five trustees" is a claim about
    `_headcount`. Vouching has no shape of its own, which is how it outlived `confirm`.
    """
    post_id = await _seed()

    response = client.post(
        _PREFIX,
        json={
            "entity_type": "post",
            "entity_id": post_id,
            "field_path": "_headcount",
            "value": 5,
            "kind": "accept",
            "sources": [{"note": "phoned the clerk"}],
        },
    )

    assert response.status_code == 200, response.text
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts.list_for_jurisdiction(cur, _OCDID)
    assert rows[0]["_is_verified"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_accepted_value_carries_its_type_across_the_wire(client):
    """`value` is jsonb, so it survives as a typed value rather than a string — the publish
    merge that applies it needs the real type, not its rendering."""
    await _seed()
    person_id = str(uuid.uuid4())

    response = client.post(
        _PREFIX,
        json={
            "entity_type": "person",
            "entity_id": person_id,
            "field_path": "name",
            "kind": "accept",
            "value": "Jane Q. Clerk",
        },
    )

    assert response.status_code == 200, response.text
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        stated = (await assertions.stated_values(cur, EntityType.PERSON, [person_id])).get(person_id, {})
    assert stated["name"][AssertionKind.ACCEPT] == ["Jane Q. Clerk"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_kind_is_rejected_by_the_model(client):
    """Validation lives in the model, so the route never reaches the CHECK constraint."""
    post_id = await _seed()

    response = client.post(
        _PREFIX,
        json={
            "entity_type": "post",
            "entity_id": post_id,
            "field_path": "_headcount",
            "value": 5,
            "kind": "vouchsafe",
        },
    )

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unattributable_assertion_is_refused(client):
    """`asserted_by` is NOT NULL by design — an assertion nobody made is not an assertion — so
    a session with no user row is turned away rather than being stored anonymously."""
    post_id = await _seed()
    global _USER_ID
    _USER_ID = None

    response = client.post(
        _PREFIX,
        json={
            "entity_type": "post",
            "entity_id": post_id,
            "field_path": "_headcount",
            "value": 5,
            "kind": "accept",
        },
    )

    assert response.status_code == 401, response.text
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT count(*) FROM assertions WHERE entity_id::text = %s", (post_id,))
        assert (await cur.fetchone())[0] == 0


async def _published_changeset() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (kind, status, jurisdiction_ocdid, arguments_json, "
            "published_at) VALUES ('scrape', 'SUCCESS', %s, '{}'::jsonb, now()) "
            "RETURNING id::text",
            (_OCDID,),
        )
        changeset_id = (await cur.fetchone())[0]
        await conn.commit()
    return changeset_id


async def _assert_field_log(entity_id: str) -> tuple:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT jurisdiction_ocdid, changeset_id FROM change_logs "
            "WHERE type = 'assert_field' AND changes->>'entity_id' = %s",
            (entity_id,),
        )
        return await cur.fetchone()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_assertion_names_its_jurisdiction_and_the_live_roster(client):
    """Without both, an assertion reaches no jurisdiction's timeline. The jurisdiction is
    resolved from `entity_type` — assuming person breaks on the first post assertion."""
    post_id = await _seed()
    changeset_id = await _published_changeset()

    response = client.post(
        _PREFIX,
        json={
            "entity_type": "post",
            "entity_id": post_id,
            "field_path": "_headcount",
            "value": 5,
            "kind": "accept",
        },
    )
    assert response.status_code == 200, response.text

    assert await _assert_field_log(post_id) == (_OCDID, changeset_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_assertion_before_any_publish_still_names_its_jurisdiction(client):
    """No live roster to join yet — the jurisdiction is still known, so the log is not orphaned
    on both counts."""
    post_id = await _seed()

    client.post(
        _PREFIX,
        json={
            "entity_type": "post",
            "entity_id": post_id,
            "field_path": "_headcount",
            "value": 5,
            "kind": "accept",
        },
    )

    assert await _assert_field_log(post_id) == (_OCDID, None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_assertion_is_logged_with_its_sources(client):
    """Assertions are current state — setting a field again overwrites it — so the log is what
    keeps the superseded value, and the only record of *why* once it has been replaced."""
    post_id = await _seed()

    for headcount in (5, 7):
        response = client.post(
            _PREFIX,
            json={
                "entity_type": "post",
                "entity_id": post_id,
                "field_path": "_headcount",
                "value": headcount,
                "kind": "accept",
                "sources": [{"note": f"clerk said {headcount}"}],
            },
        )
        assert response.status_code == 200, response.text

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changes->>'value', changes->'sources'->0->>'note' FROM change_logs "
            "WHERE type = 'assert_field' AND changes->>'entity_id' = %s "
            "ORDER BY created_at",
            (post_id,),
        )
        logged = await cur.fetchall()

    # The row itself holds only 7 now; both readings survive here.
    assert [(value, note) for value, note in logged] == [
        ("5", "clerk said 5"),
        ("7", "clerk said 7"),
    ]
