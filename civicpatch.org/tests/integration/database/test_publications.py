"""Integration tests for the publish transaction (database.publications).

Against the real test DB, because what matters here is atomicity and the `past` sweep — a
mocked cursor would prove neither. Publishing used to be a side effect of the GitHub merge
(re-reading the merged file out of open-data); these pin the behaviour now that it is a
database write.

Run with:
  mise run tcp-integration

Isolation: everything hangs off one sentinel jurisdiction, removed before and after each test.
`people` has no FK to `requests`, so it is cleaned explicitly.

`test_a_failed_publish_writes_nothing` was deleted 2026-09-22: it verified that a person the
table rejects left no half-written roster, and injected that by publishing a dict with a NULL
id. Publish takes no dicts now, and the fold only produces rows the tables accept, so the case
cannot be reached; the one transaction it relied on is still the publish's own connection.
"""
import datetime
import uuid

from tests.integration import factories

import pytest
from shared.utils.statuses import ActivityType, DismissalReason
import pytest_asyncio

from database import claims, organizations
from database import people as people_db
from database.users import SYSTEM_USER_ID
from database.database import get_pool
from database.publications import (
    UnpublishableChangeset,
    dismiss_changeset,
    publish_changeset,
)
from schemas.claims import Claim, ClaimKind, EntityType, Source

_SENTINEL_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_publish/government"
_SENTINEL_DIVISION = "ocd-division/country:us/state:zz/place:zz_publish"
_SENTINEL_USER = "zz-publish-test-user"
_CURATOR = "zz-publish-curator@example.com"


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM claims WHERE created_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_CURATOR,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_CURATOR,))
        # Publishing seats people now, so the whole posts chain has to come out first —
        # `memberships.person_id` is a FK and this file never created one before.
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_SENTINEL_OCDID,),
        )
        # Changesets first: their source records point at organizations (205: ON DELETE RESTRICT),
        # so a body cannot go while a changeset's evidence still names it.
        await cur.execute(
            "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s",
            (_SENTINEL_OCDID,),
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,)
        )
        for table in ("posts", "divisions", "organizations"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,)
            )
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,))
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,)
        )
        await cur.execute(
            "DELETE FROM activity WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture
async def sentinel_request():
    """A jurisdiction, a changeset, and the run behind it."""
    await _cleanup()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid) VALUES (%s)", (_SENTINEL_OCDID,)
        )
        # Real jurisdictions get their default organization at sync time (open_data.py); this
        # raw insert bypasses that, so it has to do the pairing itself.
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, 'Government')",
            (_SENTINEL_OCDID,),
        )
        await cur.execute(
            """
            INSERT INTO changesets (kind, jurisdiction_ocdid)
            VALUES ('scrape', %s) RETURNING id::text
            """,
            (_SENTINEL_OCDID,),
        )
        changeset_id = (await cur.fetchone())[0]
        await cur.execute(
            "UPDATE changesets SET "
            "updated_at = CURRENT_TIMESTAMP WHERE id = %s", (changeset_id,)
        )
        await conn.commit()
    yield changeset_id
    await _cleanup()


def _person(name: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "jurisdiction_ocdid": _SENTINEL_OCDID,
        "office": {"name": "Council Member", "division_ocdid": None},
        "source_urls": [],
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


_PAGE = "https://zz-publish.example/council"
_SCRAPED_AT = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
# Later reads of the same page: which one is latest is what retires somebody, so two scrapes
# cannot share a date.
_SCRAPED_AGAIN = datetime.datetime(2026, 4, 1, tzinfo=datetime.timezone.utc)
_SCRAPED_LATER = datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc)


async def _scraped(*people: dict, at: datetime.datetime = _SCRAPED_AT) -> str:
    """The records behind these people, one per phone (a page prints one number per line),
    under one published scrape. To the fold a person is their records; today's publish takes
    the dicts as given, so this changes nothing it writes."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        organization_id = await organizations.get_default(cur, _SENTINEL_OCDID)
    records = {
        str(person["id"]): [
            {
                "name": person["name"],
                "label": "Council Member",
                "source_url": _PAGE,
                "url": _PAGE,
                "organization_id": organization_id,
                "phone": phone,
            }
            for phone in (person.get("phones") or [None])
        ]
        for person in people
    }
    return await factories.published_scrape(_SENTINEL_OCDID, at, records)


async def _changeset() -> str:
    """A published-able changeset that recorded nothing."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (kind, jurisdiction_ocdid, updated_at) "
            "VALUES ('scrape', %s, now()) RETURNING id::text",
            (_SENTINEL_OCDID,),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    return row[0]


async def _people_by_status() -> dict[str, list[str]]:
    """Who is on the roster and who is not, asked of memberships.

    Read `people.status` until that column went. Same two buckets, same names — the question
    is now "does an open membership say so" rather than "does a column".
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT CASE WHEN {people_db.IS_ON_THE_ROSTER} THEN 'active' ELSE 'inactive' END,
                   name
            FROM people WHERE jurisdiction_ocdid = %s
            """,
            (_SENTINEL_OCDID,),
        )
        out: dict[str, list[str]] = {}
        for status, name in await cur.fetchall():
            out.setdefault(status, []).append(name)
        return {status: sorted(names) for status, names in out.items()}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_writes_the_roster_as_current(sentinel_request):
    ann, bob = _person("Ann"), _person("Bob")
    await _scraped(ann, bob)
    written = await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    assert written == 2
    assert await _people_by_status() == {"active": ["Ann", "Bob"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_someone_absent_from_the_roster_becomes_inactive(sentinel_request):
    """`inactive`, not deleted — seat history has to survive a person leaving office."""
    ann, bob = _person("Ann"), _person("Bob")
    await _scraped(ann, bob)
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    await _scraped(ann, at=_SCRAPED_AGAIN)
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    assert await _people_by_status() == {"active": ["Ann"], "inactive": ["Bob"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_republishing_someone_brings_them_back_to_active(sentinel_request):
    ann, bob = _person("Ann"), _person("Bob")
    await _scraped(ann, bob)
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)
    await _scraped(ann, at=_SCRAPED_AGAIN)
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    await _scraped(ann, bob, at=_SCRAPED_LATER)
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    assert await _people_by_status() == {"active": ["Ann", "Bob"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_changeset_that_read_nobody_retires_nobody(sentinel_request):
    """A scrape that found nobody is a failed scrape, not a dissolved council.

    This test verified that publishing an empty roster wrote no people. It now verifies that
    publishing a changeset with no records of its own leaves the roster standing, because
    publish takes no roster: the fold derives from every live record, and a changeset that
    recorded nothing is not a read of anything."""
    ann = _person("Ann")
    await _scraped(ann)
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    empty = await _changeset()
    assert await publish_changeset(empty, _SENTINEL_OCDID) == 1
    assert await _people_by_status() == {"active": ["Ann"]}


async def _publish_logs() -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type FROM activity WHERE jurisdiction_ocdid = %s ORDER BY created_at",
            (_SENTINEL_OCDID,),
        )
        return [row[0] for row in await cur.fetchall()]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_publish_logs_that_the_roster_changed(sentinel_request):
    """The feed every outward mirror runs on. Written on the publish cursor rather than
    best-effort afterwards, so it cannot be lost while the publish stands."""
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    assert await _publish_logs() == [ActivityType.PUBLISH_REVIEW.value]

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT changeset_id FROM activity WHERE jurisdiction_ocdid = %s",
            (_SENTINEL_OCDID,),
        )
        assert (await cur.fetchone())[0] == sentinel_request


# ── request publish state (migration 115) ────────────────────────────────────


async def _request_state(changeset_id: str) -> tuple:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT published_at, dismissed_at, resolved_by_user_id FROM changesets WHERE id = %s",
            (changeset_id,),
        )
        return await cur.fetchone()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_stamps_the_request(sentinel_request):
    """Publish state lives on the request now, not on a GitHub PR's status."""
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    published_at, dismissed_at, _ = await _request_state(sentinel_request)
    assert published_at is not None
    assert dismissed_at is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_republishing_keeps_the_first_publish_time(sentinel_request):
    """`published_at` answers "when did this go live", so a replay must not move it."""
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)
    first, _, _ = await _request_state(sentinel_request)

    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    again, _, _ = await _request_state(sentinel_request)
    assert again == first


@pytest.mark.integration
@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_dismissed_changeset_cannot_be_published(sentinel_request):
    """`DISMISSED` is terminal. A reviewer publishing a card another sweep just superseded must
    not resurrect it."""
    await dismiss_changeset(sentinel_request, DismissalReason.REJECTED)

    with pytest.raises(UnpublishableChangeset):
        await publish_changeset(sentinel_request, _SENTINEL_OCDID)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dismissing_stamps_the_request(sentinel_request):
    await dismiss_changeset(sentinel_request, DismissalReason.ERRORED)

    published_at, dismissed_at, _ = await _request_state(sentinel_request)
    assert published_at is None
    assert dismissed_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_published_request_cannot_be_dismissed(sentinel_request):
    """The CHECK forbids both being set, so dismiss refuses rather than raising: publishing
    already happened, and there is no undoing it by closing a card."""
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    await dismiss_changeset(sentinel_request, DismissalReason.ERRORED)

    published_at, dismissed_at, _ = await _request_state(sentinel_request)
    assert published_at is not None
    assert dismissed_at is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_does_not_blank_an_existing_resolver(sentinel_request):
    """A publish with no user attached must not erase who published it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (provider, provider_user_id, email, username)
            VALUES ('system', %s, %s, %s) RETURNING id::text
            """,
            (_SENTINEL_USER, f"{_SENTINEL_USER}@example.test", _SENTINEL_USER),
        )
        user_id = (await cur.fetchone())[0]
        await conn.commit()

    try:
        await publish_changeset(sentinel_request, _SENTINEL_OCDID, user_id)
        await publish_changeset(sentinel_request, _SENTINEL_OCDID)

        _, _, resolver = await _request_state(sentinel_request)
        assert str(resolver) == user_id
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            # Defensive: nothing in a clean publish asserts on this user's behalf, but
            # `created_by` is NOT NULL REFERENCES users — clear first in case that ever
            # changes, since no production path deletes a user.
            await cur.execute("DELETE FROM claims WHERE created_by = %s", (user_id,))
            await cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            await conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_machine_dismissal_is_credited_to_the_system(sentinel_request):
    """A cancelled run dismisses its own request. Since 160 that is attributed to the system
    user rather than left null: the thing that tells it apart from a person deciding not to
    publish is *who*, not *whether*."""
    await dismiss_changeset(sentinel_request, DismissalReason.ERRORED)

    _, dismissed_at, resolved_by = await _request_state(sentinel_request)
    assert dismissed_at is not None
    assert str(resolved_by) == SYSTEM_USER_ID


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dismissing_never_touches_a_published_request(sentinel_request):
    """The cancel path now fires from the shared status update, which any caller can reach.
    Publishing has to win: a late CANCELLED must not retire a roster that already went live."""
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    await dismiss_changeset(sentinel_request, DismissalReason.ERRORED)

    published_at, dismissed_at, _ = await _request_state(sentinel_request)
    assert published_at is not None
    assert dismissed_at is None


async def _seed_publisher() -> str:
    """Somebody to publish in the name of. Cleaned up with `_CURATOR` in `_cleanup`."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'email', %s, %s, 'admins') "
            "ON CONFLICT (provider, provider_user_id) DO UPDATE SET email = EXCLUDED.email "
            "RETURNING id::text",
            (_CURATOR, _CURATOR, _CURATOR.replace("@", "-")),
        )
        user_id = (await cur.fetchone())[0]
        await conn.commit()
    return user_id


async def _assert_field(person_id: str, field: str, value, kind: ClaimKind) -> None:
    """One human assertion about one field, recorded the way an edit records it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, username, role) "
            "VALUES (%s, 'email', %s, %s, 'admins') "
            "ON CONFLICT (provider, provider_user_id) DO UPDATE SET email = EXCLUDED.email "
            "RETURNING id::text",
            (_CURATOR, _CURATOR, _CURATOR.replace("@", "-")),
        )
        curator_id = (await cur.fetchone())[0]
        await claims.upsert(
            cur,
            Claim(
                entity_type=EntityType.PERSON,
                entity_id=person_id,
                field_path=field,
                kind=kind,
                value=value,
                sources=[Source(note="test")],
            ),
            curator_id,
        )
        await conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_applies_what_a_human_accepted(sentinel_request):
    """The point of the whole model: a reviewer's answer beats the scrape, and beats it at
    publish rather than at ingest — so the scrape stays what the source said, and the judgement
    is re-applied every time instead of being baked in once."""
    person = _person("Ann")
    await _assert_field(person["id"], "name", "Ann Rodriguez", ClaimKind.ACCEPT)

    await _scraped(person)
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name FROM people WHERE id::text = %s", (person["id"],))
        assert (await cur.fetchone())[0] == "Ann Rodriguez"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_drops_a_rejected_value_but_keeps_the_rest(sentinel_request):
    """A rejection suppresses one value, never the field. The wrong number stays gone however
    often it is scraped; a number nobody has judged still gets through."""
    person = {**_person("Bob"), "phones": ["(206) 555-0001", "(206) 555-9999"]}
    await _assert_field(person["id"], "phones", "(206) 555-0001", ClaimKind.REJECT)

    await _scraped(person)
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT phones FROM people WHERE id::text = %s", (person["id"],))
        assert (await cur.fetchone())[0] == ["(206) 555-9999"]


async def _accepted_for(person_id: str) -> list[tuple[str, object]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT field_path, value FROM claims "
            "WHERE entity_type = 'person' AND entity_id::text = %s AND kind = 'accept' "
            "ORDER BY field_path, value",
            (person_id,),
        )
        return [(row[0], row[1]) for row in await cur.fetchall()]


@pytest_asyncio.fixture
async def sentinel_hand_edit():
    """The same jurisdiction, but the changeset is a hand edit rather than a scrape."""
    await _cleanup()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid) VALUES (%s)", (_SENTINEL_OCDID,)
        )
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, 'Government')",
            (_SENTINEL_OCDID,),
        )
        await cur.execute(
            """
            INSERT INTO changesets (kind, jurisdiction_ocdid)
            VALUES ('people_edit', %s) RETURNING id::text
            """,
            (_SENTINEL_OCDID,),
        )
        changeset_id = (await cur.fetchone())[0]
        await conn.commit()
    yield changeset_id
    await _cleanup()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_hand_edit_does_not_vouch_for_the_rest_of_the_roster(sentinel_hand_edit):
    """Publishing asserts nothing on its own — only `claims_from_edit`, at edit time, does.
    A hand edit that touches one field must not leave every other field looking accepted."""
    user_id = await _seed_publisher()
    person = {**_person("Ann"), "phones": ["(206) 555-0001"]}

    await publish_changeset(sentinel_hand_edit, _SENTINEL_OCDID, user_id)

    assert await _accepted_for(person["id"]) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_publish_somebody_made_is_verified(sentinel_request):
    """`published_at` says it went live; `verified_at` says a person stood behind it. The
    column shipped in 185 with nothing writing it, so every publish read as unverified."""
    user_id = await _seed_publisher()

    await publish_changeset(sentinel_request, _SENTINEL_OCDID, user_id)

    assert await _verified_at(sentinel_request) is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unattended_publish_is_not_verified(sentinel_request):
    """A clean scrape publishing itself read nothing and judged nothing — the same rule that
    stops it asserting values."""
    await publish_changeset(sentinel_request, _SENTINEL_OCDID)

    assert await _verified_at(sentinel_request) is None


async def _verified_at(changeset_id: str):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT verified_at FROM changesets WHERE id::text = %s", (changeset_id,)
        )
        return (await cur.fetchone())[0]
