"""The parquet sink: which objects one state produces, and what is inside them.

Real Postgres, fake R2. The database half has to be real because what is under test is that the
seven queries and the seven declared schemas agree on live rows — the failure mode is a column
the query returns that the schema does not name, which no fixture would reproduce faithfully.
The R2 half is a recorder: `put_object` is one call with a key and a body, and what matters is
the key layout and that the body is a readable parquet file.

**What faking storage cannot catch**, and only a real write will: that the credential is scoped
to the CDN bucket. `lib/buckets.py` warns an unscoped one 403s on every call, and neither dev
container has storage configured at all (`STORAGE_ENDPOINT` is `NO_KEY_PROVIDED`), so the
upload path is unproven outside this recorder.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import io
import uuid
from datetime import datetime, timezone

import pyarrow.parquet as pq
import pytest
import pytest_asyncio

from database import divisions, organizations, posts
from database.database import get_pool
from services.sinks import parquet as parquet_sink

_ZZ = "ocd-jurisdiction/country:us/state:zz/place:zz_parquet/government"
_ZZ_DIVISION = "ocd-division/country:us/state:zz/place:zz_parquet"
_SEEN = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _Recorder:
    """An R2 client that remembers what it was asked to store."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str):
        self.objects[Key] = Body


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_ZZ,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_ZZ,)
            )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_ZZ,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed(count: int, closed: int = 0):
    """`count` people holding a seat each; the first `closed` of them have left."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_ZZ,),
        )
        organization_id = await organizations.find_or_create(cur, _ZZ)
        await divisions.find_or_create(cur, _ZZ_DIVISION, _ZZ)
        post_id = await posts.find_or_create(
            cur, _ZZ, organization_id, "mayor", _ZZ_DIVISION
        )
        for index in range(count):
            person_id = str(uuid.uuid4())
            await cur.execute(
                "INSERT INTO people (id, jurisdiction_ocdid, name, emails) "
                "VALUES (%s, %s, %s, %s)",
                (person_id, _ZZ, f"Person {index}", [f"p{index}@zz.gov"]),
            )
            await cur.execute(
                "INSERT INTO memberships "
                "(post_id, organization_id, person_id, first_seen_at, last_seen_at, closed_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    post_id,
                    organization_id,
                    person_id,
                    _SEEN,
                    _SEEN,
                    _SEEN if index < closed else None,
                ),
            )
        await conn.commit()


async def _sync() -> _Recorder:
    from unittest.mock import patch

    recorder = _Recorder()
    with patch("lib.storage.get_client", return_value=recorder):
        await parquet_sink.sync_all()
    return recorder


@pytest.mark.asyncio
@pytest.mark.integration
async def test_one_file_per_table_plus_a_manifest():
    """Not one file per state. Partitioning meant a full scan opened a footer per state, and
    these tables are small enough that the round trips cost more than the pruning saved."""
    await _seed(2)

    recorder = await _sync()

    assert "parquet/people/data.parquet" in recorder.objects
    assert "parquet/memberships/data.parquet" in recorder.objects
    assert "parquet/manifest.json" in recorder.objects
    assert not any("state=" in key for key in recorder.objects)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_every_declared_table_round_trips_from_live_rows():
    """The real point of an integration test here: the query and the schema are written in two
    different files, and only live rows prove they agree."""
    await _seed(3)

    recorder = await _sync()

    for key, body in recorder.objects.items():
        if key.endswith(".json"):
            continue
        table = pq.read_table(io.BytesIO(body))
        assert table.num_rows > 0, key


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_closed_seat_is_published_and_marked():
    """The reason to publish memberships at all: a former officeholder stays legible. Open-data
    git renders the live roster only, so this sink is the one that carries the history."""
    await _seed(3, closed=1)

    recorder = await _sync()
    seats = pq.read_table(
        io.BytesIO(recorder.objects["parquet/memberships/data.parquet"])
    )

    assert seats.num_rows == 3
    assert seats.column("is_open").to_pylist().count(False) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_lists_stay_lists():
    """What separates this from the sheet, which would render `emails` as `"a | b"`."""
    await _seed(1)

    recorder = await _sync()
    people = pq.read_table(
        io.BytesIO(recorder.objects["parquet/people/data.parquet"])
    )

    assert str(people.schema.field("emails").type) == "list<element: string>"
    assert people.column("emails").to_pylist() == [["p0@zz.gov"]]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_column_is_published_for_filtering():
    """The column replaces the partition path. Without it `WHERE state = 'wa'` has nothing to
    prune on, and the whole reason one file is affordable disappears."""
    await _seed(2)

    people = pq.read_table(
        io.BytesIO((await _sync()).objects["parquet/people/data.parquet"])
    )

    assert people.column("state").to_pylist() == ["zz", "zz"]
