"""Integration tests for `source_records` (database.source_records).

Against the real test DB, because the things worth checking are the ones a mock cannot show:
that both foreign keys hold, that the append-only grain really does allow a replay to add a
second row for the same person and scrape, and that `parsed` round-trips as jsonb.

Run with:
  mise run tcp-integration

Isolation: every test writes under one sentinel request, and clean_source_records removes
that request and its rows (which cascade) before and after each test.
"""
import pytest
import pytest_asyncio
from psycopg.errors import ForeignKeyViolation

from database.database import get_pool
from database.source_records import (
    get_source_records_for_request,
    insert_source_records,
)
from shared.schemas import Role, RoleConfig, RoleStatus
from shared.utils.taxonomy import build_taxonomy

_SENTINEL_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_test/government"

TAXONOMY = build_taxonomy(
    RoleConfig(
        roles=[
            Role(id="mayor", label="Mayor", status=RoleStatus.ACTIVE, priority=10),
            Role(
                id="council-member",
                label="Council Member",
                status=RoleStatus.ACTIVE,
                priority=500,
            ),
        ]
    )
)


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
async def test_stores_raw_beside_its_derivation(sentinel_request):
    await insert_source_records(
        sentinel_request,
        _SENTINEL_OCDID,
        _records("Ann", "Council Member Place 3 (East Ward)"),
        TAXONOMY,
    )

    rows = await get_source_records_for_request(sentinel_request)
    assert len(rows) == 1
    assert [r["label"] for r in rows[0]["raw"]] == ["Council Member Place 3 (East Ward)"]
    assert rows[0]["parsed"]["role"] == "Council Member"
    assert rows[0]["parsed"]["other_designations"] == ["Place 3"]
    assert rows[0]["parsed"]["division_ocdid"].endswith("/ward:east")
    # Publication is an event, not an inference from a NULL column.
    assert rows[0]["published_at"] is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_replay_adds_a_row_rather_than_being_rejected(sentinel_request):
    """The reason there is no unique(request_id, person_id): a parser fix must be able to
    write a fresh derivation for the same person and scrape, leaving the original intact."""
    records = _records("Ann", "Council Member Place 3")
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, records, TAXONOMY)
    await insert_source_records(sentinel_request, _SENTINEL_OCDID, records, TAXONOMY)

    rows = await get_source_records_for_request(sentinel_request)
    assert len(rows) == 2
    assert {r["person_id"] for r in rows} == {"person-ann"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unresolved_labels_are_queryable_out_of_parsed(sentinel_request):
    """`source_records` is the candidate feed — triage reads unmatched terms from `parsed`
    rather than a separate collection path."""
    await insert_source_records(
        sentinel_request,
        _SENTINEL_OCDID,
        {**_records("Bob", "City Attorney"), **_records("Cass", "Mayor")},
        TAXONOMY,
    )

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT person_id FROM source_records
            WHERE request_id = %s AND parsed -> 'unmatched' @> '["City Attorney"]'::jsonb
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
            TAXONOMY,
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_records_writes_nothing(sentinel_request):
    assert await insert_source_records(sentinel_request, _SENTINEL_OCDID, {}, TAXONOMY) == 0
    assert await get_source_records_for_request(sentinel_request) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_sighting_of_one_person_lands_in_a_single_row(sentinel_request):
    """The grain the table exists at. `parsed` *is* the reconciliation — one winning role
    across every label — so a row per sighting would parse each alone and throw that away."""
    await insert_source_records(
        sentinel_request,
        _SENTINEL_OCDID,
        _records("Dee", "Council Member", "Mayor"),
        TAXONOMY,
    )

    rows = await get_source_records_for_request(sentinel_request)

    assert len(rows) == 1
    assert [r["label"] for r in rows[0]["raw"]] == ["Council Member", "Mayor"]
    # Both pages kept: which sighting came from where is the thing a flat roster loses.
    assert [r["source_url"] for r in rows[0]["raw"]] == [
        "https://zz.gov/0",
        "https://zz.gov/1",
    ]
    # Priority decided across the group, not per label.
    assert rows[0]["parsed"]["role"] == "Mayor"
    assert sorted(rows[0]["parsed"]["roles"]) == ["Council Member", "Mayor"]
    assert [p["label"] for p in rows[0]["parsed"]["parts"]] == ["Council Member", "Mayor"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_resolved_photo_urls_ride_on_parsed_not_raw(sentinel_request):
    """`raw` keeps the pipeline's `local://` placeholder, which resolves only against a zip
    that is gone by the time anyone reads this. The resolution is a derivation, so it belongs
    with the others — and it is what lets a roster be rebuilt without `data_json`."""
    records = {
        "person-eve": [
            {
                "name": "Eve",
                "label": "Mayor",
                "source_url": "https://zz.gov/0",
                "image": "local://abc123.png",
            }
        ]
    }

    await insert_source_records(
        sentinel_request,
        _SENTINEL_OCDID,
        records,
        TAXONOMY,
        {"person-eve": {"image": "https://zz.gov/eve.png",
                        "cdn_image": "https://cdn.example/eve.png"}},
    )

    rows = await get_source_records_for_request(sentinel_request)

    assert rows[0]["raw"][0]["image"] == "local://abc123.png"
    assert rows[0]["parsed"]["image"] == "https://zz.gov/eve.png"
    assert rows[0]["parsed"]["cdn_image"] == "https://cdn.example/eve.png"
    # The parse is untouched by the images riding alongside it.
    assert rows[0]["parsed"]["role"] == "Mayor"
