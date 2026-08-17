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

from database.database import get_pool
from database.publications import publish_request

_SENTINEL_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_publish/government"


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
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
            "SELECT status, data->>'name' FROM people WHERE jurisdiction_ocdid = %s",
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
