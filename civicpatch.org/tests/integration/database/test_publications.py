"""Integration tests for the publish transaction (database.publications).

Against the real test DB, because what matters here is atomicity and the `past` sweep — a
mocked cursor would prove neither. Publishing used to be a side effect of the GitHub merge
(re-reading the merged file out of open-data); these pin the behaviour now that it is a
database write.

Run with:
  mise run tcp-integration

Isolation: everything hangs off one sentinel jurisdiction, removed before and after each test.
`people` has no FK to `requests`, so it is cleaned explicitly.
"""
import uuid

import pytest
import pytest_asyncio
from psycopg.errors import NotNullViolation

from database import assertions
from database.database import get_pool
from database.publications import dismiss_request, publish_request
from schemas.assertions import Assertion, AssertionKind, EntityType

_SENTINEL_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_publish/government"
_SENTINEL_USER = "zz-publish-test-user"
_CURATOR = "zz-publish-curator@example.com"


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM assertions WHERE asserted_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_CURATOR,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_CURATOR,))
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,))
        await cur.execute("DELETE FROM requests WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,))
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture
async def sentinel_request():
    """A jurisdiction, a request, and the pipeline run `scraped_at` is stamped from."""
    await _cleanup()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid) VALUES (%s)", (_SENTINEL_OCDID,)
        )
        await cur.execute(
            """
            INSERT INTO requests (request_type, jurisdiction_ocdid, arguments_json)
            VALUES ('people', %s, '{}'::jsonb) RETURNING id::text
            """,
            (_SENTINEL_OCDID,),
        )
        request_id = (await cur.fetchone())[0]
        await cur.execute(
            "INSERT INTO pipeline_runs (request_id, status) VALUES (%s, 'done')", (request_id,)
        )
        await conn.commit()
    yield request_id
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


async def _people_by_status() -> dict[str, list[str]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT status, name FROM people WHERE jurisdiction_ocdid = %s",
            (_SENTINEL_OCDID,),
        )
        out: dict[str, list[str]] = {}
        for status, name in await cur.fetchall():
            out.setdefault(status, []).append(name)
        return {status: sorted(names) for status, names in out.items()}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_writes_the_roster_as_current(sentinel_request):
    written = await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann"), _person("Bob")])

    assert written == 2
    assert await _people_by_status() == {"active": ["Ann", "Bob"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_someone_absent_from_the_roster_becomes_inactive(sentinel_request):
    """`inactive`, not deleted — seat history has to survive a person leaving office."""
    ann, bob = _person("Ann"), _person("Bob")
    await publish_request(sentinel_request, _SENTINEL_OCDID, [ann, bob])

    await publish_request(sentinel_request, _SENTINEL_OCDID, [ann])

    assert await _people_by_status() == {"active": ["Ann"], "inactive": ["Bob"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_republishing_someone_brings_them_back_to_active(sentinel_request):
    ann, bob = _person("Ann"), _person("Bob")
    await publish_request(sentinel_request, _SENTINEL_OCDID, [ann, bob])
    await publish_request(sentinel_request, _SENTINEL_OCDID, [ann])

    await publish_request(sentinel_request, _SENTINEL_OCDID, [ann, bob])

    assert await _people_by_status() == {"active": ["Ann", "Bob"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_empty_roster_does_not_retire_everyone(sentinel_request):
    """A scrape that found nobody is a failed scrape, not a dissolved council."""
    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])

    assert await publish_request(sentinel_request, _SENTINEL_OCDID, []) == 0
    assert await _people_by_status() == {"active": ["Ann"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_stamps_scraped_at_from_the_pipeline_run(sentinel_request):
    """Moved out of publish_side_effects — it is now atomic with the people write."""
    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.scraped_at = pr.created_at
            FROM jurisdictions j, pipeline_runs pr
            WHERE j.jurisdiction_ocdid = %s AND pr.request_id = %s
            """,
            (_SENTINEL_OCDID, sentinel_request),
        )
        assert (await cur.fetchone())[0] is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_failed_publish_writes_nothing(sentinel_request):
    """One transaction: a person the table rejects must not leave the roster half-written."""
    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])

    broken = _person("Cass")
    broken["id"] = None  # people.id is NOT NULL
    with pytest.raises(NotNullViolation):
        await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Bob"), broken])

    # Bob was in the same executemany as the rejected row, so he must not have landed.
    assert await _people_by_status() == {"active": ["Ann"]}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_does_not_stamp_published_at(sentinel_request):
    """Pins the 2026-08-16 deferral: `published_at` stays empty until the model settles, so
    this asserts the absence rather than leaving it to be assumed."""
    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM source_records WHERE published_at IS NOT NULL"
        )
        assert (await cur.fetchone())[0] == 0


# ── request publish state (migration 115) ────────────────────────────────────


async def _request_state(request_id: str) -> tuple:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT published_at, dismissed_at, resolved_by_user_id FROM requests WHERE id = %s",
            (request_id,),
        )
        return await cur.fetchone()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_stamps_the_request(sentinel_request):
    """Publish state lives on the request now, not on a GitHub PR's status."""
    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])

    published_at, dismissed_at, _ = await _request_state(sentinel_request)
    assert published_at is not None
    assert dismissed_at is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_republishing_keeps_the_first_publish_time(sentinel_request):
    """`published_at` answers "when did this go live", so a replay must not move it."""
    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])
    first, _, _ = await _request_state(sentinel_request)

    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])

    again, _, _ = await _request_state(sentinel_request)
    assert again == first


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dismissing_stamps_the_request(sentinel_request):
    await dismiss_request(sentinel_request)

    published_at, dismissed_at, _ = await _request_state(sentinel_request)
    assert published_at is None
    assert dismissed_at is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_published_request_cannot_be_dismissed(sentinel_request):
    """The CHECK forbids both being set, so dismiss refuses rather than raising: publishing
    already happened, and there is no undoing it by closing a card."""
    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])

    await dismiss_request(sentinel_request)

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
            INSERT INTO users (provider, provider_user_id, email)
            VALUES ('system', %s, %s) RETURNING id::text
            """,
            (_SENTINEL_USER, f"{_SENTINEL_USER}@example.test"),
        )
        user_id = (await cur.fetchone())[0]
        await conn.commit()

    try:
        await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")], user_id)
        await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")], None)

        _, _, resolver = await _request_state(sentinel_request)
        assert str(resolver) == user_id
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            # Publishing accepts every value on the roster in this user's name, and
            # `asserted_by` is NOT NULL — no production path deletes a user, but this one has
            # to unwind its own.
            await cur.execute("DELETE FROM assertions WHERE asserted_by = %s", (user_id,))
            await cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            await conn.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_machine_dismissal_records_no_user(sentinel_request):
    """A cancelled run dismisses its own request, and `resolved_by_user_id IS NULL` is what
    tells that apart from a person deciding not to publish."""
    await dismiss_request(sentinel_request)

    _, dismissed_at, resolved_by = await _request_state(sentinel_request)
    assert dismissed_at is not None
    assert resolved_by is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dismissing_never_touches_a_published_request(sentinel_request):
    """The cancel path now fires from the shared status update, which any caller can reach.
    Publishing has to win: a late CANCELLED must not retire a roster that already went live."""
    await publish_request(sentinel_request, _SENTINEL_OCDID, [_person("Ann")])

    await dismiss_request(sentinel_request)

    published_at, dismissed_at, _ = await _request_state(sentinel_request)
    assert published_at is not None
    assert dismissed_at is None


async def _seed_publisher() -> str:
    """Somebody to publish in the name of. Cleaned up with `_CURATOR` in `_cleanup`."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'email', %s, 'admins') "
            "ON CONFLICT (provider, provider_user_id) DO UPDATE SET email = EXCLUDED.email "
            "RETURNING id::text",
            (_CURATOR, _CURATOR),
        )
        user_id = (await cur.fetchone())[0]
        await conn.commit()
    return user_id


async def _assert_field(person_id: str, field: str, value, kind: AssertionKind) -> None:
    """One human assertion about one field, recorded the way an edit records it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'email', %s, 'admins') "
            "ON CONFLICT (provider, provider_user_id) DO UPDATE SET email = EXCLUDED.email "
            "RETURNING id::text",
            (_CURATOR, _CURATOR),
        )
        curator_id = (await cur.fetchone())[0]
        await assertions.upsert(
            cur,
            Assertion(
                entity_type=EntityType.PERSON,
                entity_id=person_id,
                field_path=field,
                kind=kind,
                value=value,
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
    await _assert_field(person["id"], "name", "Ann Rodriguez", AssertionKind.ACCEPT)

    await publish_request(sentinel_request, _SENTINEL_OCDID, [person])

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name FROM people WHERE id::text = %s", (person["id"],))
        assert (await cur.fetchone())[0] == "Ann Rodriguez"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publish_drops_a_rejected_value_but_keeps_the_rest(sentinel_request):
    """A rejection suppresses one value, never the field. The wrong number stays gone however
    often it is scraped; a number nobody has judged still gets through."""
    person = {**_person("Bob"), "phones": ["(555) 0001", "(555) 9999"]}
    await _assert_field(person["id"], "phones", "(555) 0001", AssertionKind.REJECT)

    await publish_request(sentinel_request, _SENTINEL_OCDID, [person])

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT phones FROM people WHERE id::text = %s", (person["id"],))
        assert (await cur.fetchone())[0] == ["(555) 9999"]


async def _accepted_for(person_id: str) -> list[tuple[str, object]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT field_path, value FROM assertions "
            "WHERE entity_type = 'person' AND entity_id::text = %s AND kind = 'accept' "
            "ORDER BY field_path, value",
            (person_id,),
        )
        return [(row[0], row[1]) for row in await cur.fetchall()]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_accepts_the_values_the_reviewer_saw(sentinel_request):
    """What replaced `confirm`. Nobody has to remember to vouch for a field — publishing a
    roster is somebody saying its values stand, so every field carries who last did.

    One row per *element* on a list field, which is what lets a reviewer reject one phone number
    later without restating the others.
    """
    user_id = await _seed_publisher()
    person = {**_person("Ann"), "phones": ["(555) 0001", "(555) 0002"]}

    await publish_request(sentinel_request, _SENTINEL_OCDID, [person], user_id)

    assert await _accepted_for(person["id"]) == [
        ("name", "Ann"),
        ("phones", "(555) 0001"),
        ("phones", "(555) 0002"),
    ]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_republishing_the_same_roster_adds_no_rows(sentinel_request):
    """Re-stating a value moves its timestamp rather than adding a row, which is what keeps the
    table bounded by distinct values instead of by how often anyone publishes."""
    user_id = await _seed_publisher()
    person = _person("Ann")

    for _ in range(3):
        await publish_request(sentinel_request, _SENTINEL_OCDID, [person], user_id)

    assert await _accepted_for(person["id"]) == [("name", "Ann")]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unattended_publish_asserts_nothing(sentinel_request):
    """A GitHub merge or an automated publish read nothing and judged nothing — and
    `asserted_by` is NOT NULL, because an assertion nobody made is not an assertion."""
    person = _person("Ann")

    await publish_request(sentinel_request, _SENTINEL_OCDID, [person], None)

    assert await _accepted_for(person["id"]) == []
