"""Route-level integration tests for the organization endpoints.

TestClient against the real test DB with auth mocked, so the full HTTP → Pydantic → DB stack
runs. Same approach as test_posts.py; a different sentinel place (`zz_orgs`, not `zz_route`)
so the two files' setup/teardown never touch the same jurisdiction row.

No GET here to test: this router is create/update/delete only — reads go through
`GET /api/v1/posts/{jurisdiction_ocdid}` (test_posts.py), which already returns every
organization nested with its posts. Effects are verified with a direct DB read instead.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from database.database import get_pool
from lib.auth import get_optional_user
from routers.api import organizations as organizations_router
from schemas.common import Identity

_PREFIX = "/api/v1/organizations"
_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_orgs/government"
_DEFAULT_ORG_NAME = "Government"


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
    app.include_router(organizations_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: _fake_admin()
    return TestClient(app)


@pytest.fixture
def anonymous_client():
    """No identity at all — a logged-out visitor. Every other client here is a fake admin, so
    this is the only one that can see an auth gate come back."""
    app = FastAPI()
    app.include_router(organizations_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: None
    return TestClient(app)


def _fake_default_user() -> Identity:
    return Identity(
        type="session",
        provider="email",
        provider_user_id="route-test-default",
        email="route-test-default@example.com",
        role="default",
        user_id=None,
    )


@pytest.fixture
def default_role_client():
    """Signed in, no elevated role — too low a tier for any organization write (maintainer+,
    unlike creating a post)."""
    app = FastAPI()
    app.include_router(organizations_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: _fake_default_user()
    return TestClient(app)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        for table in ("organizations", "divisions", "people"):
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
        # Every real jurisdiction gets its default organization at sync time (migration 195 /
        # open_data.py); this raw insert has to do that pairing itself.
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, %s)",
            (_OCDID, _DEFAULT_ORG_NAME),
        )
        await conn.commit()
    yield
    await _wipe()


async def _rows() -> list[tuple[str, str, str | None]]:
    """(id, name, url) for every organization on the sentinel jurisdiction — the direct-DB
    check this file uses instead of a GET, since the router has none. See module docstring."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, name, url FROM organizations WHERE jurisdiction_ocdid = %s "
            "ORDER BY sort_order, name",
            (_OCDID,),
        )
        return await cur.fetchall()


async def _default_org_id() -> str:
    for org_id, name, _ in await _rows():
        if name == _DEFAULT_ORG_NAME:
            return org_id
    raise AssertionError("sentinel jurisdiction has no default organization")


def _create(client, name: str = "School Board", **body):
    return client.post(f"{_PREFIX}/{_OCDID}", json={"name": name, **body})


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_ocdid_survives_the_round_trip(client):
    """`:path` is what lets the ocdid's slashes through, and it carries colons too. A plain
    `{jurisdiction_ocdid}` would 404 every real id."""
    response = _create(client)
    assert response.status_code == 200, response.text

    names = [name for _, name, _ in await _rows()]
    assert names == [_DEFAULT_ORG_NAME, "School Board"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_creating_the_same_name_twice_is_a_conflict(client):
    """409 rather than a second row: the identity is the (jurisdiction, name) pair, so a
    duplicate is the caller wanting a body that exists, not a new one."""
    assert _create(client).status_code == 200

    duplicate = _create(client)
    assert duplicate.status_code == 409, duplicate.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_creating_without_signing_in_is_refused(anonymous_client):
    assert _create(anonymous_client).status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_creating_an_organization_requires_maintainer_or_above(default_role_client):
    """Unlike creating a post, which any signed-in user may do, an organization is a
    structural change to how a jurisdiction's bodies are divided — maintainer+."""
    assert _create(default_role_client).status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_updating_requires_maintainer(client, default_role_client):
    org_id = _create(client).json()["data"]["id"]

    response = default_role_client.patch(
        f"{_PREFIX}/{org_id}", json={"name": "Renamed", "url": None}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_updating_changes_name_and_url(client):
    org_id = _create(client).json()["data"]["id"]

    response = client.patch(
        f"{_PREFIX}/{org_id}", json={"name": "Renamed", "url": "https://example.com"}
    )
    assert response.status_code == 200, response.text

    renamed = next(row for row in await _rows() if row[0] == org_id)
    assert renamed[1:] == ("Renamed", "https://example.com")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_updating_a_missing_organization_is_404(client):
    response = client.patch(
        f"{_PREFIX}/00000000-0000-0000-0000-000000000000",
        json={"name": "Anything", "url": None},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_setting_the_default_requires_maintainer(client, default_role_client):
    org_id = _create(client).json()["data"]["id"]

    response = default_role_client.post(f"{_PREFIX}/{org_id}/default")
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_setting_the_default_is_not_mistaken_for_creating_an_organization(client):
    """The create route takes a greedy `:path`; registered first, it would read this as a new
    body for the jurisdiction `{id}/default`."""
    org_id = _create(client).json()["data"]["id"]

    response = client.post(f"{_PREFIX}/{org_id}/default")
    assert response.status_code == 200, response.text

    names = [name for _, name, _ in await _rows()]
    assert names == [_DEFAULT_ORG_NAME, "School Board"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_setting_a_missing_organization_as_default_is_404(client):
    response = client.post(f"{_PREFIX}/00000000-0000-0000-0000-000000000000/default")
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deleting_requires_maintainer(client, default_role_client):
    org_id = _create(client).json()["data"]["id"]

    response = default_role_client.delete(f"{_PREFIX}/{org_id}")
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deleting_an_empty_non_default_organization_succeeds(client):
    org_id = _create(client).json()["data"]["id"]

    response = client.delete(f"{_PREFIX}/{org_id}")
    assert response.status_code == 200, response.text

    assert org_id not in {row[0] for row in await _rows()}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deleting_the_default_organization_is_refused(client):
    """Every jurisdiction must always have one — migration 195's invariant."""
    default_id = await _default_org_id()
    response = client.delete(f"{_PREFIX}/{default_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deleting_an_organization_with_posts_is_refused(client):
    org_id = _create(client).json()["data"]["id"]
    division_ocdid = _OCDID.replace("jurisdiction", "division").replace("/government", "")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # posts.division_ocdid FKs to divisions — a real post-creation call finds-or-creates
        # this on the way (database/posts.py's own docstring); this raw insert has to do it
        # itself.
        await cur.execute(
            "INSERT INTO divisions (ocdid, jurisdiction_ocdid) VALUES (%s, %s)",
            (division_ocdid, _OCDID),
        )
        await cur.execute(
            "INSERT INTO posts (jurisdiction_ocdid, organization_id, role_id, division_ocdid) "
            "VALUES (%s, %s, 'mayor', %s)",
            (_OCDID, org_id, division_ocdid),
        )
        await conn.commit()

    response = client.delete(f"{_PREFIX}/{org_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deleting_a_missing_organization_is_404(client):
    response = client.delete(f"{_PREFIX}/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
