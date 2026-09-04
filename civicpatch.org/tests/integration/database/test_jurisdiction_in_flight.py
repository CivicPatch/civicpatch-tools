"""Integration tests for what a jurisdiction is still waiting on.

Real Postgres: both lanes are SQL predicates spliced from `database.changesets`, and
`AVAILABLE_FOR_REVIEW` turns on an EXISTS against `source_records` — none of which a unit test
can exercise honestly.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.changesets import get_in_flight
from database.database import get_pool
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_in_flight/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # source_records cascade with their changeset, so the changesets delete covers them.
        await cur.execute(
            "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        # This row only — `state = 'zz'` is shared with every other sentinel suite.
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    yield
    await _wipe()


async def _seed_jurisdiction() -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
            VALUES (%s, 'zz', '{}'::jsonb, now())
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (_OCDID,),
        )


async def _changeset(kind: str, status: str | None) -> str:
    """`changesets_scrape_has_a_run` ties the two: a scrape has a status, nothing else may."""
    await _seed_jurisdiction()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO changesets (kind, jurisdiction_ocdid)
            VALUES (%s, %s)
            RETURNING id::text
            """,
            (kind, _OCDID),
        )
        changeset_id = (await cur.fetchone())[0]
        if status is not None:
            # A status means a run: migration 169 moved it off the changeset, and
            # `RUN_IN_FLIGHT` now asks whether that run has finished.
            await cur.execute(
                """
                INSERT INTO pipeline_runs
                    (id, jurisdiction_ocdid, status, finished_at, changeset_id)
                VALUES (%s, %s, %s,
                        CASE WHEN %s = ANY(%s) THEN now() END, %s)
                """,
                (
                    changeset_id,
                    _OCDID,
                    status,
                    status,
                    [s.value for s in TERMINAL_PIPELINE_RUN_STATUSES],
                    changeset_id,
                ),
            )
        return changeset_id


async def _add_sighting(changeset_id: str) -> None:
    """What puts a changeset in the review pool — `AVAILABLE_FOR_REVIEW` is an EXISTS on this."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO source_records
                (changeset_id, jurisdiction_ocdid, name, label, source_url)
            VALUES (%s::uuid, %s, 'Ada Lovelace', 'Mayor', 'https://example.test')
            """,
            (changeset_id, _OCDID),
        )


async def _publish(changeset_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE changesets SET published_at = now() WHERE id::text = %s",
            (changeset_id,),
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_running_scrape_is_in_flight_but_not_awaiting_review():
    """The lanes are disjoint: a scrape still running has written no sightings yet, so it
    cannot satisfy `AVAILABLE_FOR_REVIEW`."""
    changeset_id = await _changeset("scrape", "SCRAPE_PAGE")

    result = await get_in_flight(_OCDID)

    assert [entry.changeset_id for entry in result.in_flight] == [changeset_id]
    assert result.in_flight[0].is_running is True
    assert result.in_flight[0].awaiting_review is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_finished_scrape_with_sightings_awaits_review():
    changeset_id = await _changeset("scrape", "SUCCESS")
    await _add_sighting(changeset_id)

    result = await get_in_flight(_OCDID)

    assert [entry.changeset_id for entry in result.in_flight] == [changeset_id]
    assert result.in_flight[0].is_running is False
    assert result.in_flight[0].awaiting_review is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_import_awaits_review_with_no_pipeline_run():
    """76% of changesets are imports. They never have a status, so the running lane can never
    hold one — this is the case a name like `PipelineRunChangeset` would have mislabelled."""
    changeset_id = await _changeset("sheet_import", None)
    await _add_sighting(changeset_id)

    result = await get_in_flight(_OCDID)

    assert [entry.changeset_id for entry in result.in_flight] == [changeset_id]
    assert result.in_flight[0].is_running is False
    assert result.in_flight[0].awaiting_review is True
    assert result.in_flight[0].pipeline_run_status is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_finished_scrape_with_no_sightings_is_in_neither_lane():
    """It produced nothing and is not running, so nobody is waiting on it. It still counts
    toward the total — it happened."""
    await _changeset("scrape", "SUCCESS")

    result = await get_in_flight(_OCDID)

    assert result.in_flight == []
    assert result.total_changesets == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_resolved_changeset_is_not_in_flight():
    changeset_id = await _changeset("scrape", "SUCCESS")
    await _add_sighting(changeset_id)
    await _publish(changeset_id)

    result = await get_in_flight(_OCDID)

    assert result.in_flight == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_last_published_at_is_the_latest_publish_not_the_latest_row():
    """A changeset published today may have been created before one published last week, so
    this is `max(published_at)` rather than the newest row's."""
    older = await _changeset("scrape", "SUCCESS")
    newer = await _changeset("scrape", "SUCCESS")
    await _publish(newer)
    await _publish(older)  # published second, so it holds the later timestamp

    result = await get_in_flight(_OCDID)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT published_at FROM changesets WHERE id::text = %s", (older,)
        )
        expected = (await cur.fetchone())[0]

    assert result.last_published_at == expected.isoformat()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_total_counts_every_changeset_not_just_the_unresolved_ones():
    await _changeset("scrape", "SCRAPE_PAGE")
    published = await _changeset("scrape", "SUCCESS")
    await _publish(published)
    await _changeset("sheet_import", None)

    result = await get_in_flight(_OCDID)

    assert result.total_changesets == 3
    assert len(result.in_flight) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_jurisdiction_with_no_changesets_answers_emptily():
    """Never scraped is a real state, not an error — the page renders an empty section."""
    await _seed_jurisdiction()

    result = await get_in_flight(_OCDID)

    assert result.in_flight == []
    assert result.last_published_at is None
    assert result.total_changesets == 0
