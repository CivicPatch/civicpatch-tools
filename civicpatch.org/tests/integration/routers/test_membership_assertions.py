"""Route-level integration tests for the removal claims.

`PUT /memberships/{id}/assertion`. What publish then
does with these claims is covered at the database layer
(`tests/integration/database/test_post_derivation.py`); these cover what only crosses the wire:
that the endpoint files the claim the fold reads, that `none` takes it back, and who is allowed
to say any of it. `closed` and `never_held` are the same claim now, and the choice between them
goes with the enum at step 9.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.post_derivation import DerivedMembership
from database import assertions, divisions, organizations, posts
from database.database import get_pool
from core.people_edits import POSTS_FIELD
from lib.auth import get_optional_user
from routers.api import memberships as memberships_router
from routers.api import people as people_router
from schemas.assertions import AssertionKind, EntityType
from schemas.common import Identity
from tests.integration import factories

_MEMBERSHIPS = "/api/v1/memberships"
_PEOPLE = "/api/v1/people"
_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_claims/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_claims"
_EMAIL = "zz-claims-route@example.com"
_SEEN_AT = "2026-06-15T00:00:00Z"

_USER_ID: str | None = None


def _identity(role: str) -> Identity:
    return Identity(
        type="session",
        provider="email",
        provider_user_id=_EMAIL,
        email=_EMAIL,
        role=role,
        user_id=_USER_ID,
    )


def _app(role: str) -> TestClient:
    app = FastAPI()
    app.include_router(memberships_router.get_router(), prefix=_MEMBERSHIPS)
    app.include_router(people_router.get_router(), prefix=_PEOPLE)
    app.dependency_overrides[get_optional_user] = lambda: _identity(role)
    return TestClient(app)


@pytest.fixture
def client():
    return _app("admins")


@pytest.fixture
def default_role_client():
    """Signed in, lowest rung of the trust ladder."""
    return _app("default")


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM assertions WHERE created_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_EMAIL,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_EMAIL,))
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        await cur.execute("DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,))
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
    global _USER_ID
    await _wipe()
    yield
    _USER_ID = None
    await _wipe()


async def _seed() -> tuple[str, str]:
    """A signed-in user, and one person holding one membership. Returns person and membership."""
    global _USER_ID
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'email', %s, %s, 'admins') RETURNING id::text",
            (_EMAIL, _EMAIL, _EMAIL.replace("@", "-")),
        )
        _USER_ID = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id, _OCDID, "Claims Route"),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)
        membership_id = await factories.bind_membership(
            cur,
            DerivedMembership(person_id=person_id),
            post_id,
            organization_id,
            _SEEN_AT,
        )
        await conn.commit()
    return person_id, membership_id


async def _seeded_post_id() -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        return (await cur.fetchone())[0]


async def _posts_claimed(person_id: str, kind: AssertionKind) -> list:
    """Which posts somebody has been said to hold, or not hold. The claim is about the person:
    the membership row is rewritten at every publish, so nothing can address it."""
    claims = await _claims(EntityType.PERSON, person_id)
    return claims.get(POSTS_FIELD, {}).get(kind) or []


async def _claims(entity_type: EntityType, entity_id: str) -> dict:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return (await assertions.asserted_values(cur, entity_type, [entity_id])).get(
            entity_id, {}
        )


async def _open_membership_count(person_id: str) -> int:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM memberships WHERE person_id = %s AND closed_at IS NULL",
            (person_id,),
        )
        return (await cur.fetchone())[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_removal_files_a_claim_rather_than_writing_the_row(client):
    """This test verified that `closed` filed a `closed_at` accept. It now verifies that a
    removal files a reject of the post, because `closed` is gone ("they left" and "the page was
    wrong" end a membership the same way, §17) and because which posts somebody holds is a
    claim about the person, which is what publish re-derives from."""
    person_id, membership_id = await _seed()

    response = client.put(
        f"{_MEMBERSHIPS}/{membership_id}/assertion", json={"assertion": "closed"}
    )

    assert response.status_code == 200, response.text
    assert await _posts_claimed(person_id, AssertionKind.REJECT) == [
        await _seeded_post_id()
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_reason_rides_as_the_claim_s_source(client):
    """"Phoned the clerk" belongs beside the claim it justifies, not in a column of its own."""
    person_id, membership_id = await _seed()

    client.put(
        f"{_MEMBERSHIPS}/{membership_id}/assertion",
        json={"assertion": "closed", "reason": "phoned the clerk, she retired in May"},
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # Scoped to this person: `posts` rejects are filed by every roster edit now, so an
        # unscoped read answers with whatever else the suite has done.
        await cur.execute(
            "SELECT sources FROM assertions "
            "WHERE entity_type = 'person' AND entity_id::text = %s AND field_path = %s "
            "  AND kind = 'reject' AND withdrawn_at IS NULL",
            (person_id, POSTS_FIELD),
        )
        rows = await cur.fetchall()
    assert [row[0] for row in rows] == [
        [{"note": "phoned the clerk, she retired in May", "url": None}]
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_choosing_none_on_a_membership_nobody_removed_claims_nothing(client):
    """This test verified that `none` took a removal back. It now verifies that `none` on an
    unremoved membership claims nothing, because a removed one has no row left to address: the
    writer derives the roster and does not keep a rejected membership. Putting somebody back is
    a fresh accept of the post (`PUT /memberships`), which outranks the reject as the newest
    claim, and step 9's route addresses the pair rather than the row."""
    person_id, membership_id = await _seed()

    client.put(f"{_MEMBERSHIPS}/{membership_id}/assertion", json={"assertion": "none"})

    assert await _posts_claimed(person_id, AssertionKind.REJECT) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_assertion_is_rejected_by_the_model(client):
    _, membership_id = await _seed()

    response = client.put(
        f"{_MEMBERSHIPS}/{membership_id}/assertion", json={"assertion": "banished"}
    )

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_any_signed_in_user_may_claim_a_removal(default_role_client):
    """Same tier as publishing a roster, which already closes memberships by omission. Gating the
    withdrawable claim above the unwithdrawable publish would protect nothing."""
    _, membership_id = await _seed()

    response = default_role_client.put(
        f"{_MEMBERSHIPS}/{membership_id}/assertion", json={"assertion": "closed"}
    )

    assert response.status_code == 200, response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deleting_the_person_stays_out_of_reach(default_role_client):
    """The line these claims exist to stay on the safe side of: deleting destroys history and
    nothing re-derives it, so it is maintainers-only."""
    person_id, _ = await _seed()

    response = default_role_client.delete(f"{_PEOPLE}/{person_id}")

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_claiming_a_removal_requires_signing_in():
    app = FastAPI()
    app.include_router(memberships_router.get_router(), prefix=_MEMBERSHIPS)
    app.dependency_overrides[get_optional_user] = lambda: None
    anonymous = TestClient(app)
    _, membership_id = await _seed()

    response = anonymous.put(
        f"{_MEMBERSHIPS}/{membership_id}/assertion", json={"assertion": "closed"}
    )

    assert response.status_code == 403, response.text
    assert await _claims(EntityType.MEMBERSHIP, membership_id) == {}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unattributable_claim_is_refused(client):
    """`assertions.created_by` is NOT NULL: a claim nobody made is not a claim, so a session with
    no user row is turned away rather than stored anonymously."""
    global _USER_ID
    _, membership_id = await _seed()
    _USER_ID = None

    response = client.put(
        f"{_MEMBERSHIPS}/{membership_id}/assertion", json={"assertion": "closed"}
    )

    assert response.status_code == 401, response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_by_person_read_names_the_organization_and_the_live_claim(client):
    """What the person editor renders from: memberships grouped under the organization they are
    in, each row naming its organization so the screen never has to guess.

    This test verified that a rejected membership still listed, marked `never_held`. It now
    verifies that it is gone from the list, because the writer derives the roster from the facts
    and a rejected membership is not on it."""
    _, membership_id = await _seed()

    rows = client.get(f"{_MEMBERSHIPS}/{_OCDID}").json()["data"]["memberships"]
    assert len(rows) == 1
    assert rows[0]["organization_name"]
    assert rows[0]["organization_id"]

    client.put(f"{_MEMBERSHIPS}/{membership_id}/assertion", json={"assertion": "never_held"})

    assert client.get(f"{_MEMBERSHIPS}/{_OCDID}").json()["data"]["memberships"] == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unclaimed_membership_reads_as_none(client):
    await _seed()

    rows = client.get(f"{_MEMBERSHIPS}/{_OCDID}").json()["data"]["memberships"]

    assert rows[0]["removal_assertion"] == "none"
