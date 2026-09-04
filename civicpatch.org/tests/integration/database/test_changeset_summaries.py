"""Integration tests for the cross-state changeset summary.

Real Postgres: every figure here is a `FILTER` arm or a CTE, so none of it can be checked by
unit-testing a mapper. What is worth locking down is the arithmetic — which outcomes land in
which column, and which rows are counted once versus several times.

Isolation: sentinel state 'zy', its own state code so the rollup's per-state grouping can be
asserted without another suite's fixtures leaking into the row.
"""

import pytest
import pytest_asyncio

from database.changeset_summaries import (
    BUCKET_FAILED,
    BUCKET_OK,
    BUCKET_REVIEW,
    get_state_bucket,
    get_state_calendar,
    get_state_rollup,
)
from database.database import get_pool
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES
from shared.utils.statuses import ChangeLogType, DismissalReason

_STATE = "zy"
_OCDID = f"ocd-jurisdiction/country:us/state:{_STATE}/place:zy_one/government"
_OCDID_TWO = f"ocd-jurisdiction/country:us/state:{_STATE}/place:zy_two/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_OCDID, _OCDID_TWO):
            await cur.execute(
                "DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            await cur.execute(
                "DELETE FROM source_records WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            await cur.execute(
                "DELETE FROM pipeline_runs WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            await cur.execute(
                "DELETE FROM changesets WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            await cur.execute(
                "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,)
            )


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    await _wipe()
    yield
    await _wipe()


async def _seed_jurisdiction(ocdid: str = _OCDID) -> None:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions (jurisdiction_ocdid, state, data, updated_at)
            VALUES (%s, %s, %s::jsonb, now())
            ON CONFLICT (jurisdiction_ocdid) DO NOTHING
            """,
            (ocdid, _STATE, '{"name": "Zy Place"}'),
        )


async def _changeset(
    ocdid: str = _OCDID,
    *,
    kind: str = "scrape",
    status: str | None = "SUCCESS",
    published: bool = False,
    reason: DismissalReason | None = None,
    days_ago: int = 1,
    with_records: bool = True,
) -> str:
    """One changeset in a chosen end state.

    `with_records` seeds a `source_records` row because `AVAILABLE_FOR_REVIEW` is
    `EXISTS (source_records)` — a pending changeset without one is not in the queue.
    """
    await _seed_jurisdiction(ocdid)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO changesets (kind, jurisdiction_ocdid, created_at, updated_at, published_at, dismissed_at, dismissed_reason)
            VALUES (%s, %s, now() - make_interval(days => %s), now() - make_interval(days => %s), CASE WHEN %s THEN now() END, CASE WHEN %s::text IS NOT NULL THEN now() END, %s)
            RETURNING id::text
            """,
            (kind, ocdid, days_ago, days_ago, published, reason, reason),
        )
        changeset_id = (await cur.fetchone())[0]
        if status is not None:
            # A status means a run; the run carries its own jurisdiction.
            await cur.execute(
                """
                INSERT INTO pipeline_runs
                    (id, jurisdiction_ocdid, status, finished_at, changeset_id)
                VALUES (%s, %s, %s, CASE WHEN %s = ANY(%s) THEN now() END, %s)
                """,
                (
                    changeset_id,
                    ocdid,
                    status,
                    status,
                    [s.value for s in TERMINAL_PIPELINE_RUN_STATUSES],
                    changeset_id,
                ),
            )
        if with_records:
            await cur.execute(
                """
                INSERT INTO source_records (changeset_id, jurisdiction_ocdid, name, label,
                                            source_url)
                VALUES (%s, %s, 'Someone', 'Mayor', 'https://example.test')
                """,
                (changeset_id, ocdid),
            )
    return changeset_id


async def _row():
    return next(r for r in await get_state_rollup() if r.state == _STATE)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_only_a_publish_counts_as_confirmed():
    """A re-confirmed roster is a healthy outcome, and it reaches here as a publish — that is
    the whole reason it publishes rather than being dismissed. A dismissal is not a success."""
    await _changeset(published=True)
    await _changeset(reason=DismissalReason.REJECTED)

    assert (await _row()).confirmed == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_rejected_and_errored_are_counted_apart():
    """They share the Failed bucket but mean opposite things: one says the data was bad, the
    other that the run broke. The badge says which, so the query has to keep them apart."""
    await _changeset(reason=DismissalReason.REJECTED)
    await _changeset(reason=DismissalReason.ERRORED)

    row = await _row()
    assert (row.rejected, row.errored) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_queue_counts_one_changeset_per_jurisdiction():
    """Only one review per jurisdiction is valid. `supersede_stacked_requests` maintains that
    as a sweep, so duplicates exist transiently — counting rows instead of jurisdictions read
    Maine at 1,542 against a true 586."""
    await _changeset(days_ago=9)
    await _changeset(days_ago=2)

    row = await _row()
    assert row.to_review == 1
    # The newest by `updated_at` is the valid one, so the age is its, not the loser's.
    assert row.oldest_days == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_queue_is_not_windowed():
    """A changeset waiting 90 days is still waiting, and it is the one this page exists to
    surface. Windowing the queue hid 58% of it in the benchmark."""
    await _changeset(days_ago=200)

    row = await _row()
    assert row.to_review == 1
    assert row.oldest_days == 200


@pytest.mark.asyncio
@pytest.mark.integration
async def test_review_lifecycle_is_not_a_roster_edit():
    """`publish_review` and `dismiss_review` say what happened to the *review*, which the outcome
    already reports. Counting them inflated roster edits by ~72% on dev."""
    changeset_id = await _changeset(published=True)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for type_ in (ChangeLogType.ADD_PERSON, ChangeLogType.PUBLISH_REVIEW):
            await cur.execute(
                """
                INSERT INTO change_logs (type, jurisdiction_ocdid, changeset_id, changes)
                VALUES (%s, %s, %s, '{}'::jsonb)
                """,
                (type_, _OCDID, changeset_id),
            )

    assert (await _row()).roster_edits == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_still_going_is_counted_unwindowed():
    """It gates the scrape button. A run started before the window is still running, and
    missing it would offer to start a second batch on top of a live one."""
    await _changeset(status="RUNNING", days_ago=200)

    assert (await _row()).running == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_finished_run_is_not_still_going():
    await _changeset(status="SUCCESS", published=True)

    assert (await _row()).running == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_calendar_bands_a_day_by_what_became_of_its_runs():
    await _changeset(published=True, days_ago=3)
    await _changeset(reason=DismissalReason.ERRORED, days_ago=3)
    await _changeset(days_ago=3)

    day = next(d for d in await get_state_calendar() if d.state == _STATE and d.ok)
    assert (day.ok, day.failed, day.to_review) == (1, 1, 1)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_calendar_also_says_what_kind_ran():
    """Imports are most of what runs, so a day reading "2 ok" without saying no scraper
    produced them would mislead."""
    await _changeset(published=True, days_ago=4)
    await _changeset(published=True, days_ago=4, kind="sheet_import", status=None)

    day = next(d for d in await get_state_calendar() if d.state == _STATE and d.ok == 2)
    assert (day.scrapes, day.imports) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_hand_edit_is_not_a_collection_attempt():
    """`ok` and `failed` describe a run reading a source. A `people_edit` has no run — 8 dev
    rows, none with a status — so counting it would pad the green band with something that
    never ran, and `jurisdiction_edit` could never be "to review" at all."""
    await _changeset(published=True, kind="people_edit", status=None, days_ago=6)

    row = await _row()
    assert row.confirmed == 0
    assert not [d for d in await get_state_calendar() if d.state == _STATE]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_bucket_counts_localities_where_the_rollup_counts_changesets():
    """Deliberately different numbers. One jurisdiction scraped twice is two confirmed runs and
    one place to look at, so the modal's pager must read its total from the bucket — computing
    "+N more" from the rollup would promise rows the list cannot reach."""
    await _changeset(published=True, days_ago=2)
    await _changeset(published=True, days_ago=3)

    assert (await _row()).confirmed == 2
    page = await get_state_bucket(_STATE, BUCKET_OK, limit=10)
    assert page.total == 1
    assert [r.jurisdiction_ocdid for r in page.rows] == [_OCDID]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_review_bucket_leads_with_the_longest_wait():
    """The queue is drained oldest-end first, so burying the 90-day item on the last page
    defeats the bucket."""
    await _seed_jurisdiction(_OCDID_TWO)
    await _changeset(_OCDID, days_ago=2)
    await _changeset(_OCDID_TWO, days_ago=40)

    page = await get_state_bucket(_STATE, BUCKET_REVIEW, limit=10)
    assert [r.jurisdiction_ocdid for r in page.rows] == [_OCDID_TWO, _OCDID]
    assert page.rows[0].days_waiting == 40


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_failed_bucket_says_which_kind_of_failure():
    """Rejected and errored share the bucket, so the row has to carry the distinction the
    bucket label drops."""
    await _changeset(reason=DismissalReason.REJECTED)

    page = await get_state_bucket(_STATE, BUCKET_FAILED, limit=10)
    assert [r.failure_reason for r in page.rows] == ["rejected"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_bucket_returns_nothing_rather_than_everything():
    """The bucket name reaches SQL as a value, so a typo or a stale link must fail closed."""
    await _changeset(published=True)

    page = await get_state_bucket(_STATE, "not-a-bucket", limit=10)
    assert (page.total, page.rows) == (0, [])
