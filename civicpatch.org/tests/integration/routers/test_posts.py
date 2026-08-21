"""Route-level integration tests for the post endpoints.

TestClient against the real test DB with auth mocked, so the full HTTP → Pydantic → DB stack
runs. The DB-layer tests pass Python values straight in and never cross the wire; everything
here is a contract only this layer can see — path conversion, query coercion, status codes,
and the shape that actually reaches a consumer.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import memberships, organizations, posts
from database.database import get_pool
from lib.auth import get_optional_user
from routers.api import posts as posts_router
from schemas.common import Identity

_PREFIX = "/api/v1/posts"
_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_route/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_route"
_WARD_3 = f"{_BASE}/ward:3"


def _fake_admin() -> Identity:
    return Identity(
        type="session",
        provider="email",
        provider_user_id="route-test-admin",
        email="route-test@example.com",
        role="admins",
        user_id=None,
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(posts_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: _fake_admin()
    return TestClient(app)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        await cur.execute(
            "DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (_OCDID,)
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


def _create(client, role_id: str = "mayor", division: str = _BASE, **body):
    return client.post(
        f"{_PREFIX}/{_OCDID}",
        json={"role_id": role_id, "division_ocdid": division, **body},
    )


async def _change_logs() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type, changes FROM change_logs WHERE jurisdiction_ocdid = %s "
            "ORDER BY created_at",
            (_OCDID,),
        )
        return [{"type": r[0], **(r[1] or {})} for r in await cur.fetchall()]


async def _seat_someone(post_id: str) -> None:
    """Give a post a member, so it reads as verified and refuses deletion."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, data) VALUES (%s, %s, '{}')",
            (person_id, _OCDID),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await memberships.record(
            cur, person_id, post_id, organization_id, "2026-06-15T00:00:00Z"
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_ocdid_survives_the_round_trip(client):
    """`:path` is what lets the ocdid's slashes through, and it carries colons too. A plain
    `{jurisdiction_ocdid}` would 404 every real id."""
    assert _create(client).status_code == 200

    response = client.get(f"{_PREFIX}/{_OCDID}")

    assert response.status_code == 200, response.text
    organizations_out = response.json()["data"]["organizations"]
    assert len(organizations_out) == 1
    assert [p["role_id"] for p in organizations_out[0]["posts"]] == ["mayor"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_creating_the_same_seat_twice_is_a_conflict(client):
    """409 rather than a second row: the identity triple is the whole key, so a duplicate is
    the caller wanting a post that exists, not a new one."""
    assert _create(client).status_code == 200

    duplicate = _create(client)

    assert duplicate.status_code == 409, duplicate.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patch_and_delete_reach_a_post_not_the_jurisdiction_route(client):
    """`/{post_id}` and `/{jurisdiction_ocdid:path}` share a prefix. A path converter matches
    greedily, so if these ever land on the wrong handler it happens silently — a 200 from the
    wrong route looks exactly like success."""
    post_id = _create(client).json()["data"]["id"]

    patched = client.patch(f"{_PREFIX}/{post_id}", json={"label": "Town Mayor", "headcount": 2})
    assert patched.status_code == 200, patched.text

    listed = client.get(f"{_PREFIX}/{_OCDID}").json()["data"]["organizations"][0]["posts"][0]
    assert listed["label"] == "Town Mayor"
    assert listed["headcount"] == 2

    assert client.delete(f"{_PREFIX}/{post_id}").status_code == 200
    assert client.get(f"{_PREFIX}/{_OCDID}").json()["data"]["organizations"][0]["posts"] == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_patching_a_post_that_is_not_there_is_404(client):
    missing = client.patch(f"{_PREFIX}/{uuid.uuid4()}", json={"label": "x", "headcount": 1})

    assert missing.status_code == 404, missing.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_seat_someone_has_held_cannot_be_deleted(client):
    """History, including closed memberships. The FK would refuse anyway — this is what makes
    it a 409 the caller can act on rather than a 500."""
    post_id = _create(client).json()["data"]["id"]
    await _seat_someone(post_id)

    refused = client.delete(f"{_PREFIX}/{post_id}")

    assert refused.status_code == 409, refused.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_verified_is_on_the_wire_both_ways(client):
    """The flag is only useful if it survives serialisation, and absence must never be how a
    consumer infers it."""
    unheld = _create(client).json()["data"]["id"]
    held = _create(client, role_id="clerk").json()["data"]["id"]
    await _seat_someone(held)

    posts_out = client.get(f"{_PREFIX}/{_OCDID}").json()["data"]["organizations"][0]["posts"]

    by_id = {p["id"]: p for p in posts_out}
    assert by_id[held]["_verified"] is True
    assert by_id[unheld]["_verified"] is False
    assert "verified" not in by_id[held]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_as_of_is_coerced_from_the_query_string(client):
    """FastAPI parses `?as_of=YYYY-MM-DD` into a date. The DB tests hand in a Python date and
    never cross that boundary, so this is the only place the conversion is exercised."""
    post_id = _create(client).json()["data"]["id"]
    await _seat_someone(post_id)

    def holders(query: str) -> int:
        response = client.get(f"{_PREFIX}/{_OCDID}{query}")
        assert response.status_code == 200, response.text
        return response.json()["data"]["organizations"][0]["posts"][0]["holders"]

    assert holders("") == 1
    assert holders("?as_of=2026-07-01") == 1
    assert holders("?as_of=2026-01-01") == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_seat_for_nobody_is_rejected(client):
    """`headcount` is `gt=0`. Validation lives in the model, so the route never sees a zero —
    but nothing had ever sent one to find out."""
    rejected = _create(client, division=_WARD_3, headcount=0)

    assert rejected.status_code == 422, rejected.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_identity_triple_is_not_patchable(client):
    """`role_id` and `division_ocdid` are the key. Accepting either here would let a rename
    fork the post — the next scrape would mint a second rather than match this one."""
    post_id = _create(client).json()["data"]["id"]

    client.patch(f"{_PREFIX}/{post_id}", json={"label": "x", "headcount": 1, "role_id": "clerk"})

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        assert (await posts.get(cur, post_id))["role_id"] == "mayor"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_every_write_leaves_a_trace(client):
    """Who created a seat and who removed it. `roles.py`, `people.py` and `pull_requests.py`
    all log; posts did not, so a curator's edits were unattributable."""
    post_id = _create(client).json()["data"]["id"]
    client.patch(f"{_PREFIX}/{post_id}", json={"label": "Town Mayor", "headcount": 2})
    client.delete(f"{_PREFIX}/{post_id}")

    logs = await _change_logs()

    assert [log["type"] for log in logs] == ["add_post", "edit_post", "delete_post"]
    assert all(log["post_id"] == post_id for log in logs)
    assert {f["field"] for f in logs[1]["fields"]} == {"label", "headcount"}
    assert logs[2]["label"] == "Town Mayor"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_rejected_create_leaves_no_trace(client):
    """409 means no seat was created. Logging it would put an event in the feed for something
    that never happened."""
    _create(client)
    _create(client)

    assert [log["type"] for log in await _change_logs()] == ["add_post"]
