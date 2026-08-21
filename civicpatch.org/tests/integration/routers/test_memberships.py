"""Route-level integration tests for the membership endpoints.

TestClient against the real test DB with auth mocked. The DB-layer tests call `assign`
directly; these are the only ones that exercise the payload model, the status codes, and the
shape a consumer actually receives.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import json
import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database import divisions, memberships, organizations, posts
from database.database import get_pool
from lib.auth import get_optional_user
from routers.api import memberships as memberships_router
from schemas.common import Identity

_PREFIX = "/api/v1/memberships"
_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_mroute/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_mroute"
_WARD_3 = f"{_BASE}/ward:3"
_SEEN_AT = "2026-06-15T00:00:00Z"


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
    app.include_router(memberships_router.get_router(), prefix=_PREFIX)
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
    yield
    await _wipe()


async def _seed() -> tuple[str, str, str]:
    """A person and two seats in one body to move between."""
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, data) VALUES (%s, %s, %s)",
            (person_id, _OCDID, json.dumps({"name": "Route Test"})),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await divisions.find_or_create(cur, _WARD_3, _OCDID)
        mayor = await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)
        ward = await posts.find_or_create(
            cur, _OCDID, organization_id, "council-member", _WARD_3
        )
        await conn.commit()
    return person_id, mayor, ward


@pytest.mark.asyncio
@pytest.mark.integration
async def test_seating_someone_reports_no_move(client):
    person_id, mayor, _ = await _seed()

    response = client.put(_PREFIX, json={"person_id": person_id, "post_id": mayor})

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["moved_from"] is None
    assert body["membership_id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_move_names_the_seat_it_came_from(client):
    """`moved_from` is what lets the UI say "moved from X" rather than "assigned". A move
    leaves a closed row behind, and the curator has to know it did."""
    person_id, mayor, ward = await _seed()
    client.put(_PREFIX, json={"person_id": person_id, "post_id": mayor})

    moved = client.put(_PREFIX, json={"person_id": person_id, "post_id": ward})

    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["moved_from"] == mayor


@pytest.mark.asyncio
@pytest.mark.integration
async def test_seating_into_a_post_that_is_not_there_is_404(client):
    """`UnknownPost` has to become a status code. Uncaught it is a 500, which reads to the
    caller as our fault rather than a bad post id."""
    person_id, _, _ = await _seed()

    missing = client.put(
        _PREFIX, json={"person_id": person_id, "post_id": str(uuid.uuid4())}
    )

    assert missing.status_code == 404, missing.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_seat_with_no_person_is_rejected(client):
    _, mayor, _ = await _seed()

    rejected = client.put(_PREFIX, json={"post_id": mayor})

    assert rejected.status_code == 422, rejected.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unmatched_text_reaches_the_wire_with_its_counts(client):
    """The triage list is only actionable if the counts and example jurisdictions survive
    serialisation — a bare list of strings would not tell a curator where to look."""
    person_id, mayor, _ = await _seed()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await memberships.record(
            cur,
            person_id,
            mayor,
            organization_id,
            _SEEN_AT,
            unmatched_text=["Zz Route Liaison"],
        )
        await conn.commit()

    response = client.get(f"{_PREFIX}/unmatched")

    assert response.status_code == 200, response.text
    rows = response.json()["data"]["unmatched_text"]
    row = next(r for r in rows if r["text"] == "Zz Route Liaison")
    assert row["occurrences"] == 1
    assert row["jurisdictions"] == 1
    assert row["examples"] == [_OCDID]


async def _change_logs() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type, changes FROM change_logs WHERE jurisdiction_ocdid = %s "
            "ORDER BY created_at",
            (_OCDID,),
        )
        return [{"type": r[0], **(r[1] or {})} for r in await cur.fetchall()]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_assignment_and_a_move_are_one_type_told_apart_by_the_payload(client):
    """Splitting them into two types would put the distinction in a place the feed has to
    special-case. `moved_from` carries it, and it is also the fact worth reading — a move left
    a closed row behind."""
    person_id, mayor, ward = await _seed()

    client.put(_PREFIX, json={"person_id": person_id, "post_id": mayor})
    client.put(_PREFIX, json={"person_id": person_id, "post_id": ward})

    logs = await _change_logs()

    assert [log["type"] for log in logs] == ["assign_membership"] * 2
    assert logs[0]["moved_from"] is None
    assert logs[1]["moved_from"] == mayor
    assert logs[0]["person_name"] == "Route Test"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_failed_assignment_leaves_no_trace(client):
    """404 means nobody was assigned."""
    person_id, _, _ = await _seed()

    client.put(_PREFIX, json={"person_id": person_id, "post_id": str(uuid.uuid4())})

    assert await _change_logs() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unmatched_is_not_swallowed_by_the_jurisdiction_route(client):
    """Both are GET on this router and `:path` matches greedily, so declaration order is the
    only thing keeping "unmatched" from being read as a jurisdiction ocdid. Reversed, this
    returns an empty membership list with a 200 — a silent wrong answer, not an error."""
    await _seed()

    response = client.get(f"{_PREFIX}/unmatched")

    assert response.status_code == 200, response.text
    assert "unmatched_text" in response.json()["data"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_person_axis_read_names_the_person(client):
    """Screen 4 lists by person, so an id is not enough — the join is what makes the row
    renderable without a second lookup per row."""
    person_id, mayor, _ = await _seed()
    client.put(_PREFIX, json={"person_id": person_id, "post_id": mayor, "label": "Mayor"})

    response = client.get(f"{_PREFIX}/{_OCDID}")

    assert response.status_code == 200, response.text
    rows = response.json()["data"]["memberships"]
    assert len(rows) == 1
    assert rows[0]["person_name"] == "Route Test"
    assert rows[0]["role_id"] == "mayor"
    assert rows[0]["label"] == "Mayor"
