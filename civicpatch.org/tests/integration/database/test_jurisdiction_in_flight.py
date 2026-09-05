"""Integration tests for what a jurisdiction is still waiting on.

Real Postgres: both lanes are SQL predicates spliced from `database.changesets`, and
`AVAILABLE_FOR_REVIEW` turns on an EXISTS against `source_records` — none of which a unit test
can exercise honestly.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import pytest
import pytest_asyncio

from database.changesets import get_in_flight, register_scrape_changeset
from database.database import get_pool
from database.pipeline_runs import update_pipeline_run_status
from schemas.common import InFlightEntryType
from shared.utils.statuses import PipelineRunStatus
from tests.integration import factories

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


async def _a_scrape(status: str) -> str:
    """A scrape's proposal, minted by a run the way ingest does, then reporting `status`.

    Returns the changeset. The run keeps its own id, which is the shape production writes.
    """
    await factories.seed_jurisdiction(_OCDID, "zz")
    run_id = await factories.start_run(_OCDID)
    changeset_id = await register_scrape_changeset(run_id)
    await update_pipeline_run_status(run_id, status)
    return changeset_id


async def _an_import() -> str:
    """A changeset with no run behind it. Nothing mints these — they arrive from a sheet."""
    await factories.seed_jurisdiction(_OCDID, "zz")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO changesets (kind, jurisdiction_ocdid)
            VALUES ('sheet_import', %s)
            RETURNING id::text
            """,
            (_OCDID,),
        )
        await conn.commit()
        return (await cur.fetchone())[0]


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
    changeset_id = await _a_scrape("SCRAPE_PAGE")

    result = await get_in_flight(_OCDID)

    assert [entry.id for entry in result.in_flight] == [changeset_id]
    assert result.in_flight[0].is_running is True
    assert result.in_flight[0].awaiting_review is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_that_has_not_reached_ingest_yet_is_still_in_flight():
    """The case the "In progress" section exists for, and the one the test above cannot reach:
    it seeds the changeset first. A real run mints none until ingest, so for its whole life
    before that a changeset-rooted query reports the jurisdiction idle while it is scraping."""
    await factories.seed_jurisdiction(_OCDID, "zz")
    run_id = await factories.start_run(
        _OCDID, status=PipelineRunStatus.SCRAPE_PAGE, progress=40
    )

    result = await get_in_flight(_OCDID)

    assert [entry.id for entry in result.in_flight] == [run_id]
    assert result.in_flight[0].entry_type is InFlightEntryType.PIPELINE_RUN
    assert result.in_flight[0].is_running is True
    assert result.in_flight[0].awaiting_review is False
    assert result.in_flight[0].pipeline_run_status == PipelineRunStatus.SCRAPE_PAGE.value
    assert result.in_flight[0].pipeline_run_progress == 40


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_run_that_has_just_minted_its_changeset_appears_once():
    """The window between ingest and the terminal status report: the run is unfinished and its
    changeset already exists, so both lanes would match it. They split on `changeset_id`, which
    hands it to the changeset lane — still running, but reported by the id a reviewer can use."""
    await factories.seed_jurisdiction(_OCDID, "zz")
    run_id = await factories.start_run(_OCDID)
    changeset_id = await register_scrape_changeset(run_id)

    result = await get_in_flight(_OCDID)

    assert [entry.id for entry in result.in_flight] == [changeset_id]
    assert result.in_flight[0].entry_type is InFlightEntryType.CHANGESET
    assert result.in_flight[0].is_running is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_finished_scrape_with_sightings_awaits_review():
    changeset_id = await _a_scrape("SUCCESS")
    await _add_sighting(changeset_id)

    result = await get_in_flight(_OCDID)

    assert [entry.id for entry in result.in_flight] == [changeset_id]
    assert result.in_flight[0].is_running is False
    assert result.in_flight[0].awaiting_review is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_import_awaits_review_with_no_pipeline_run():
    """76% of changesets are imports. They never have a status, so the running lane can never
    hold one — this is the case a name like `PipelineRunChangeset` would have mislabelled."""
    changeset_id = await _an_import()
    await _add_sighting(changeset_id)

    result = await get_in_flight(_OCDID)

    assert [entry.id for entry in result.in_flight] == [changeset_id]
    assert result.in_flight[0].is_running is False
    assert result.in_flight[0].awaiting_review is True
    assert result.in_flight[0].pipeline_run_status is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_finished_scrape_with_no_sightings_is_in_neither_lane():
    """It produced nothing and is not running, so nobody is waiting on it. It still counts
    toward the total — it happened."""
    await _a_scrape("SUCCESS")

    result = await get_in_flight(_OCDID)

    assert result.in_flight == []
    assert result.total_changesets == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_resolved_changeset_is_not_in_flight():
    changeset_id = await _a_scrape("SUCCESS")
    await _add_sighting(changeset_id)
    await _publish(changeset_id)

    result = await get_in_flight(_OCDID)

    assert result.in_flight == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_last_published_at_is_the_latest_publish_not_the_latest_row():
    """A changeset published today may have been created before one published last week, so
    this is `max(published_at)` rather than the newest row's."""
    older = await _a_scrape("SUCCESS")
    newer = await _a_scrape("SUCCESS")
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
    await _a_scrape("SCRAPE_PAGE")
    published = await _a_scrape("SUCCESS")
    await _publish(published)
    await _an_import()

    result = await get_in_flight(_OCDID)

    assert result.total_changesets == 3
    assert len(result.in_flight) == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_jurisdiction_with_no_changesets_answers_emptily():
    """Never scraped is a real state, not an error — the page renders an empty section."""
    await factories.seed_jurisdiction(_OCDID, "zz")

    result = await get_in_flight(_OCDID)

    assert result.in_flight == []
    assert result.last_published_at is None
    assert result.total_changesets == 0
