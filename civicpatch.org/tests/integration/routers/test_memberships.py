"""Route-level integration tests for the membership endpoints.

TestClient against the real test DB with auth mocked. The DB-layer tests call `assign`
directly; these are the only ones that exercise the payload model, the status codes, and the
shape a consumer actually receives.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.post_derivation import DerivedMembership, MembershipSource
from database import activity, divisions, memberships, organizations, posts, projection
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.jurisdictions import OfficeEdit, PersonEdit
from services.jurisdiction_edits import edit_published_roster
from lib.auth import get_optional_user
from routers.api import memberships as memberships_router
from schemas.common import Identity
from tests.integration import factories

_PREFIX = "/api/v1/memberships"
_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_mroute/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_mroute"
_WARD_3 = f"{_BASE}/ward:3"
_SEEN_AT = "2026-06-15T00:00:00Z"
_PAGE = "https://zz-mroute.example/clerk"
_READ_AT = datetime(2026, 6, 1, tzinfo=timezone.utc)


def _fake_admin() -> Identity:
    return Identity(
        type="session",
        provider="email",
        provider_user_id="route-test-admin",
        email="route-test@example.com",
        role="admins",
        user_id=None,
    )


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
def client():
    app = FastAPI()
    app.include_router(memberships_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: _fake_admin()
    return TestClient(app)


@pytest.fixture
def default_role_client():
    """Any signed-in user, no elevated role — assigning a membership is open at this tier,
    unlike `/unmatched` or creating/editing the post itself, both maintainer-only."""
    app = FastAPI()
    app.include_router(memberships_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: _fake_default_user()
    return TestClient(app)


@pytest.fixture
def anonymous_client():
    """No identity at all — a logged-out visitor."""
    app = FastAPI()
    app.include_router(memberships_router.get_router(), prefix=_PREFIX)
    app.dependency_overrides[get_optional_user] = lambda: None
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
            "DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
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


async def _seat(person_id: str, post_id: str, label: str | None = None) -> None:
    """Add an office to what somebody holds. Was `PUT /memberships`, deleted 2026-09-23.

    `offices` is the whole set, not a delta, so this reads what they hold first: seating them
    in the council without naming their clerk's post would say they hold only the council one.
    """
    # From the facts, not the table: the clerk membership the seeded record derives exists
    # only after a rebuild, and the editor reads the same roster the API serves.
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await projection.rebuild_from_facts(cur, _OCDID)
        await conn.commit()
        held = await memberships.open_memberships_for_persons(cur, [person_id])
    offices = [
        OfficeEdit(id=row["post_id"])
        for row in held
        if row["post_id"] != post_id
    ]
    offices.append(OfficeEdit(id=post_id, membership_label=label))
    await edit_published_roster(
        _OCDID, [PersonEdit(id=person_id, offices=offices)], SYSTEM_USER_ID
    )


async def _seed() -> tuple[str, str, str]:
    """A person and two posts in one organization to move between.

    The person is somebody a page named, in an organization of their own: a roster is derived
    from records, so somebody no page ever mentioned holds nothing whatever is claimed about
    them, and could not be assigned either.
    """
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await cur.execute(
            # `name` as well as `data`: since 134 the only production writer
            # (`PERSON_UPSERT`) fills both, so a fixture writing the blob alone is a row shape
            # nothing real produces.
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id, _OCDID, "Route Test"),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await divisions.find_or_create(cur, _WARD_3, _OCDID)
        mayor = await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)
        ward = await posts.find_or_create(
            cur, _OCDID, organization_id, "council-member", _WARD_3
        )
        elsewhere = await organizations.find_or_create(
            cur, _OCDID, "Office of the City Clerk"
        )
        # The post the record below derives, so the first rebuild matches it rather than
        # minting one and logging the mint.
        await posts.find_or_create(cur, _OCDID, elsewhere, "clerk", _BASE)
        await conn.commit()
    await factories.published_source_record(
        _OCDID, elsewhere, person_id, "Route Test", "Clerk", _PAGE, _READ_AT
    )
    return person_id, mayor, ward


@pytest.mark.asyncio
@pytest.mark.integration
async def test_assigning_puts_the_jurisdiction_on_the_sync_feed(client):
    """How this edit reaches open-data and the sheet. The route calls neither: `assign` writes
    a change log on its own cursor and `WriteRecentChangesWorkflow` reads it, so a seat that moved in
    the database cannot leave the published files behind."""
    person_id, mayor, _ = await _seed()

    await _seat(person_id, mayor)

    changed = await activity.jurisdictions_changed_since(15)
    assert _OCDID in [row.jurisdiction_ocdid for row in changed]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unmatched_text_reaches_the_wire_with_its_counts(client):
    """The triage list is only actionable if the counts and example jurisdictions survive
    serialisation — a bare list of strings would not tell a curator where to look."""
    person_id, mayor, _ = await _seed()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await factories.bind_membership(
            cur,
            DerivedMembership(person_id=person_id, meta_unmatched_text=["Zz Route Liaison"]),
            mayor,
            organization_id,
            _SEEN_AT,
        )
        await conn.commit()

    response = client.get(f"{_PREFIX}/unmatched")

    assert response.status_code == 200, response.text
    rows = response.json()["data"]["meta_unmatched_text"]
    row = next(r for r in rows if r["text"] == "Zz Route Liaison")
    assert row["occurrences"] == 1
    assert row["jurisdictions"] == 1
    assert row["examples"] == [_OCDID]


async def _activity_rows() -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type, changes FROM activity WHERE jurisdiction_ocdid = %s "
            "ORDER BY created_at",
            (_OCDID,),
        )
        return [{"type": r[0], **(r[1] or {})} for r in await cur.fetchall()]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_unmatched_is_not_swallowed_by_the_jurisdiction_route(client):
    """Both are GET on this router and `:path` matches greedily, so declaration order is the
    only thing keeping "unmatched" from being read as a jurisdiction ocdid. Reversed, this
    returns an empty membership list with a 200 — a silent wrong answer, not an error."""
    await _seed()

    response = client.get(f"{_PREFIX}/unmatched")

    assert response.status_code == 200, response.text
    assert "meta_unmatched_text" in response.json()["data"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_person_axis_read_names_the_person(client):
    """Screen 4 lists by person, so an id is not enough — the join is what makes the row
    renderable without a second lookup per row."""
    person_id, mayor, _ = await _seed()
    await _seat(person_id, mayor, "Mayor")

    response = client.get(f"{_PREFIX}/{_OCDID}")

    assert response.status_code == 200, response.text
    rows = response.json()["data"]["memberships"]
    [seated] = [row for row in rows if row["role_id"] == "mayor"]
    assert seated["person_name"] == "Route Test"
    assert seated["label"] == "Mayor"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_person_axis_read_names_the_organization(client):
    """The person editor groups a person's rows by the body they are in, so each row has to
    name its own. Moved here on 2026-09-23 from `test_membership_assertions.py`, whose route is
    gone; the claim it makes about this read is unchanged."""
    person_id, mayor, _ = await _seed()
    await _seat(person_id, mayor, "Mayor")

    rows = client.get(f"{_PREFIX}/{_OCDID}").json()["data"]["memberships"]

    [seated] = [row for row in rows if row["role_id"] == "mayor"]
    assert seated["organization_id"]
    assert seated["organization_name"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_both_axes_answer_the_same_moment(client):
    """The screen toggles between by-post and by-person, so a date meaning one thing on one
    axis and another on the other would make switching the view silently switch the moment."""
    person_id, mayor, _ = await _seed()
    await _seat(person_id, mayor)

    before = client.get(f"{_PREFIX}/{_OCDID}?as_of=2020-01-01")
    after = client.get(f"{_PREFIX}/{_OCDID}?as_of=2099-01-01")

    assert before.status_code == 200, before.text
    assert before.json()["data"]["memberships"] == []
    assert [row["role_id"] for row in after.json()["data"]["memberships"]] == [
        "clerk",
        "mayor",
    ]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_person_axis_read_carries_the_whole_parse(client):
    """The screen shows what the source said beside what the parser made of it. Without every
    piece on the wire the client would have to re-run the parser to explain its own rows."""
    person_id, mayor, _ = await _seed()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await factories.bind_membership(
            cur,
            DerivedMembership(
                person_id=person_id,
                sources=[MembershipSource(note="Mayor Position 8 (Zz Route Liaison)")],
                designations=["Position 8"],
                meta_unmatched_text=["Zz Route Liaison"],
            ),
            mayor,
            organization_id,
            _SEEN_AT,
        )
        await conn.commit()

    row = client.get(f"{_PREFIX}/{_OCDID}").json()["data"]["memberships"][0]

    assert row["source_labels"] == ["Mayor Position 8 (Zz Route Liaison)"]
    assert row["designations"] == ["Position 8"]
    assert row["meta_unmatched_text"] == ["Zz Route Liaison"]
    assert row["role_id"] == "mayor"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_person_axis_reads_without_signing_in(anonymous_client):
    """The other axis of the same public page. `/unmatched` stays gated — it is
    cross-jurisdiction triage rather than this page's data, and that line is the point."""
    read = anonymous_client.get(f"{_PREFIX}/{_OCDID}")
    assert read.status_code == 200, read.text
    assert read.json()["data"]["memberships"] == []

    assert anonymous_client.get(f"{_PREFIX}/unmatched").status_code == 403


# ── Seat timestamps ─────────────────────────────────────────────────────
# `opened_at` is when the facts behind a membership were observed: a scrape's run date, the
# moment of a hand edit.


async def _seat_seen_at(person_id: str, post_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT opened_at FROM memberships "
            "WHERE person_id = %s AND post_id = %s AND closed_at IS NULL",
            (person_id, post_id),
        )
        row = await cur.fetchone()
        return row[0] if row else None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_manual_seat_is_dated_when_the_human_seated_them(client):
    person_id, mayor, _ = await _seed()
    before = datetime.now(timezone.utc)

    await _seat(person_id, mayor)

    # It also checked `last_seen_at`; that column went at 228.
    assert await _seat_seen_at(person_id, mayor) >= before
