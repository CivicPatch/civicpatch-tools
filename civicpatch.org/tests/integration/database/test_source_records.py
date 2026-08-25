"""Integration tests for `source_records` (database.source_records).

Against the real test DB, because the things worth checking are the ones a mock cannot show:
that both foreign keys hold, that a record and its identity are written as a pair, and that a
label is a column something can actually query.

Run with:
  mise run tcp-integration

Isolation: every test writes under one sentinel request, and the fixture removes that request
and its rows (which cascade) before and after each test.
"""
import pytest
import pytest_asyncio
from psycopg.errors import ForeignKeyViolation

from database.database import get_pool
from database.source_records import (
    get_source_records_for_request,
    insert_source_records,
)

_SENTINEL_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_test/government"


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # source_records cascades on request delete; the jurisdiction is FK'd by both.
        await cur.execute(
            "DELETE FROM requests WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,)
        )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture
async def sentinel_request():
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
        await conn.commit()
    yield request_id
    await _cleanup()


def _records(name: str, *labels: str) -> dict:
    """One person, one sighting per label. Keyed by the id reconciliation resolved them to."""
    return {
        f"person-{name.lower()}": [
            {"name": name, "label": label, "source_url": f"https://zz.gov/{i}"}
            for i, label in enumerate(labels)
        ]
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stores_each_sighting_verbatim(sentinel_request):
    await insert_source_records(
        sentinel_request,
        _SENTINEL_OCDID,
        _records("Ann", "Council Member Place 3 (East Ward)"),
    )

    rows = await get_source_records_for_request(sentinel_request)
    assert len(rows) == 1
    # The label is stored as the page gave it — undecomposed. Nothing derived is written, so
    # a later parser fix changes what this row means without rewriting it.
    assert rows[0]["label"] == "Council Member Place 3 (East Ward)"
    assert rows[0]["name"] == "Ann"
    assert rows[0]["source_url"] == "https://zz.gov/0"
    assert rows[0]["person_id"] == "person-ann"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_replay_adds_rows_rather_than_being_rejected(sentinel_request):
    """There is no unique key: a re-submitted scrape writes fresh evidence, leaving the
    original intact."""
    records = _records("Ann", "Council Member Place 3")
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, records)
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, records)

    rows = await get_source_records_for_request(sentinel_request)
    assert len(rows) == 2
    assert {r["person_id"] for r in rows} == {"person-ann"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_labels_are_queryable_as_a_column(sentinel_request):
    """The reason the table has this shape. Finding every sighting under one label used to mean
    unnesting a jsonb array; it is now a WHERE clause against an indexed column."""
    await insert_source_records(
        sentinel_request,
        _SENTINEL_OCDID,
        {**_records("Bob", "City Attorney"), **_records("Cass", "Mayor")},
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT i.person_id
            FROM source_records s
            JOIN source_record_identities i ON i.source_record_id = s.id
            WHERE s.request_id = %s AND s.label = 'City Attorney'
            """,
            (sentinel_request,),
        )
        assert [row[0] for row in await cur.fetchall()] == ["person-bob"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_evidence_for_an_unknown_request_is_rejected():
    """The FK is what stops orphan evidence accumulating against a scrape that never ran."""
    with pytest.raises(ForeignKeyViolation):
        await insert_source_records(
            "00000000-0000-0000-0000-000000000000",
            _SENTINEL_OCDID,
            _records("Ann", "Mayor"),
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_records_writes_nothing(sentinel_request):
    assert await insert_source_records(sentinel_request, _SENTINEL_OCDID, {}) == 0
    assert await get_source_records_for_request(sentinel_request) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_sighting_of_one_person_is_its_own_row(sentinel_request):
    """The grain the table exists at. One person seen under two titles is two rows, each still
    holding the page it came from — which is what a merged row loses."""
    await insert_source_records(
        sentinel_request,
        _SENTINEL_OCDID,
        _records("Dee", "Council Member", "Mayor"),
    )

    rows = await get_source_records_for_request(sentinel_request)

    assert len(rows) == 2
    assert [r["label"] for r in rows] == ["Council Member", "Mayor"]
    assert [r["source_url"] for r in rows] == ["https://zz.gov/0", "https://zz.gov/1"]
    # Two rows, one human: the link lives in source_record_identities.
    assert {r["person_id"] for r in rows} == {"person-dee"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_photo_urls_are_stored_on_the_sighting(sentinel_request):
    """Both urls are columns: where the photo came from, and where we serve it. The pipeline's
    `local://` ref is resolved before the write, because it means nothing once the zip is gone."""
    records = {
        "person-eve": [
            {
                "name": "Eve",
                "label": "Mayor",
                "source_url": "https://zz.gov/0",
                "image": "https://zz.gov/eve.png",
                "cdn_image": "https://cdn.example/eve.png",
            }
        ]
    }

    await insert_source_records(sentinel_request, _SENTINEL_OCDID, records)

    rows = await get_source_records_for_request(sentinel_request)

    assert rows[0]["image"] == "https://zz.gov/eve.png"
    assert rows[0]["cdn_image"] == "https://cdn.example/eve.png"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_record_is_never_written_without_its_identity(sentinel_request):
    """The two inserts share a transaction. A record nothing can link to a person is evidence
    no reader would ever find."""
    await insert_source_records(
        sentinel_request, _SENTINEL_OCDID, _records("Fay", "Mayor")
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT count(*)
            FROM source_records s
            LEFT JOIN source_record_identities i ON i.source_record_id = s.id
            WHERE s.request_id = %s AND i.source_record_id IS NULL
            """,
            (sentinel_request,),
        )
        assert (await cur.fetchone())[0] == 0
