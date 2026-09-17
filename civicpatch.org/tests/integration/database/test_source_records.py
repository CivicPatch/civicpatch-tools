"""Integration tests for `source_records` (database.source_records).

Against the real test DB, because the things worth checking are the ones a mock cannot show:
that both foreign keys hold, that a record and its identity are written as a pair, and that a
label is a column something can actually query.

Run with:
  mise run tcp-integration

Isolation: every test writes under one sentinel request, and the fixture removes that request
and its rows (which cascade) before and after each test.
"""
import pathlib

import pytest
import pytest_asyncio
from psycopg.errors import ForeignKeyViolation

from database.database import get_pool
from database.organizations import delete, set_default
from database.source_records import (
    get_source_records_for_changeset,
    insert_source_records,
)

_BACKFILL = (
    pathlib.Path(__file__).parents[3]
    / "database_operations/migrations/204_source_records_organization_backfill.up.sql"
)

_SENTINEL_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_test/government"

# Real uuids: `source_record_identities.person_id` is a uuid column since 145, because a
# cluster id that is not one is `_resolution`'s ambiguous-match sentinel.
_ANN = "00000000-0000-4000-8000-000000000001"
_BOB = "00000000-0000-4000-8000-000000000002"
_DEE = "00000000-0000-4000-8000-000000000004"
_EVE = "00000000-0000-4000-8000-000000000005"


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # source_records cascades on request delete; the jurisdiction is FK'd by both.
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,)
        )
        await cur.execute("DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,))
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_SENTINEL_OCDID,))
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
            INSERT INTO changesets (kind, jurisdiction_ocdid)
            VALUES ('scrape', %s) RETURNING id::text
            """,
            (_SENTINEL_OCDID,),
        )
        changeset_id = (await cur.fetchone())[0]
        await conn.commit()
    yield changeset_id
    await _cleanup()


_IDS = {
    "ann": "00000000-0000-4000-8000-000000000001",
    "bob": "00000000-0000-4000-8000-000000000002",
    "cass": "00000000-0000-4000-8000-000000000003",
    "dee": "00000000-0000-4000-8000-000000000004",
    "fay": "00000000-0000-4000-8000-000000000005",
}


def _records(name: str, *labels: str) -> dict:
    """One person, one sighting per label. Keyed by the id reconciliation resolved them to."""
    return {
        _IDS[name.lower()]: [
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

    rows = await get_source_records_for_changeset(sentinel_request)
    assert len(rows) == 1
    # The label is stored as the page gave it — undecomposed. Nothing derived is written, so
    # a later parser fix changes what this row means without rewriting it.
    assert rows[0]["label"] == "Council Member Place 3 (East Ward)"
    assert rows[0]["name"] == "Ann"
    assert rows[0]["source_url"] == "https://zz.gov/0"
    assert rows[0]["person_id"] == _ANN


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_replay_adds_rows_rather_than_being_rejected(sentinel_request):
    """There is no unique key: a re-submitted scrape writes fresh evidence, leaving the
    original intact."""
    records = _records("Ann", "Council Member Place 3")
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, records)
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, records)

    rows = await get_source_records_for_changeset(sentinel_request)
    assert len(rows) == 2
    assert {r["person_id"] for r in rows} == {_ANN}


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
            SELECT i.person_id::text
            FROM source_records s
            JOIN source_record_identities i ON i.source_record_id = s.id
            WHERE s.changeset_id = %s AND s.label = 'City Attorney'
            """,
            (sentinel_request,),
        )
        assert [row[0] for row in await cur.fetchall()] == [_BOB]


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
    assert await get_source_records_for_changeset(sentinel_request) == []


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

    rows = await get_source_records_for_changeset(sentinel_request)

    assert len(rows) == 2
    assert [r["label"] for r in rows] == ["Council Member", "Mayor"]
    assert [r["source_url"] for r in rows] == ["https://zz.gov/0", "https://zz.gov/1"]
    # Two rows, one human: the link lives in source_record_identities.
    assert {r["person_id"] for r in rows} == {_DEE}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_photo_urls_are_stored_on_the_sighting(sentinel_request):
    """Both urls are columns: where the photo came from, and where we serve it. The pipeline's
    `local://` ref is resolved before the write, because it means nothing once the zip is gone."""
    records = {
        _EVE: [
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

    rows = await get_source_records_for_changeset(sentinel_request)

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
            WHERE s.changeset_id = %s AND i.source_record_id IS NULL
            """,
            (sentinel_request,),
        )
        assert (await cur.fetchone())[0] == 0


async def _organization(jurisdiction_ocdid: str, name: str) -> str:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid) VALUES (%s) ON CONFLICT DO NOTHING",
            (jurisdiction_ocdid,),
        )
        await cur.execute(
            "INSERT INTO organizations (jurisdiction_ocdid, name) VALUES (%s, %s) RETURNING id::text",
            (jurisdiction_ocdid, name),
        )
        organization_id = (await cur.fetchone())[0]
        await conn.commit()
    return organization_id


def _stamped(person_id: str, name: str, organization_id: str | None) -> dict:
    return {
        person_id: [
            {
                "name": name,
                "label": "Mayor",
                "source_url": "https://zz.gov/0",
                "organization_id": organization_id,
            }
        ]
    }


async def _stored_organizations(changeset_id: str) -> dict[str, str | None]:
    return {r["name"]: r["organization_id"] for r in await get_source_records_for_changeset(changeset_id)}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_current_body_of_the_jurisdiction_is_stored(sentinel_request):
    council = await _organization(_SENTINEL_OCDID, "City Council")

    await insert_source_records(sentinel_request, _SENTINEL_OCDID, _stamped(_ANN, "Ann", council))

    assert await _stored_organizations(sentinel_request) == {"Ann": council}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deleting_a_body_moves_its_evidence_to_the_default(sentinel_request):
    default = await _organization(_SENTINEL_OCDID, "Government")
    await set_default(default)
    mayor = await _organization(_SENTINEL_OCDID, "Office of the Mayor")
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, _stamped(_ANN, "Ann", mayor))

    assert await delete(mayor) == _SENTINEL_OCDID

    assert await _stored_organizations(sentinel_request) == {"Ann": default}


async def _run_backfill(changeset_organization_id: str | None) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET organization_id = %s WHERE jurisdiction_ocdid = %s",
            (changeset_organization_id, _SENTINEL_OCDID),
        )
        await cur.execute(_BACKFILL.read_text())


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_backfill_files_an_unpublished_changesets_rows_under_the_default(sentinel_request):
    await _organization(_SENTINEL_OCDID, "City Council")
    default = await _organization(_SENTINEL_OCDID, "Government")
    await set_default(default)
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, _stamped(_ANN, "Ann", None))

    await _run_backfill(None)

    assert await _stored_organizations(sentinel_request) == {"Ann": default}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_backfill_prefers_the_organization_the_changeset_was_published_in(sentinel_request):
    council = await _organization(_SENTINEL_OCDID, "City Council")
    await set_default(await _organization(_SENTINEL_OCDID, "Government"))
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, _stamped(_ANN, "Ann", None))

    await _run_backfill(council)

    assert await _stored_organizations(sentinel_request) == {"Ann": council}
