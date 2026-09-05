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
    BUCKET_DISMISSED,
    BUCKET_PUBLISHED,
    BUCKET_REVIEW,
    get_state_bucket,
    get_state_calendar,
    get_state_rollup,
)
from database.database import get_pool
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES
from shared.utils.statuses import ChangeLogType, DismissalReason
from tests.integration import factories

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
            # A status means a run. Its own id, not the changeset's — `register_scrape_changeset`
            # mints a fresh one, and sharing them is the shape that hid three broken readers.
            await cur.execute(
                """
                INSERT INTO pipeline_runs
                    (id, jurisdiction_ocdid, status, finished_at, changeset_id)
                VALUES (gen_random_uuid(), %s, %s, CASE WHEN %s = ANY(%s) THEN now() END, %s)
                """,
                (
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
async def test_only_a_publish_counts_as_published():
    """A re-confirmed roster is a healthy outcome, and it reaches here as a publish — that is
    the whole reason it publishes rather than being dismissed. A dismissal is not a success."""
    await _changeset(published=True)
    await _changeset(reason=DismissalReason.REJECTED)

    assert (await _row()).published == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_cancellation_is_counted_by_the_badge_that_lists_it():
    """The count and the list must share a *predicate*, not a total — the bucket is deduped per
    locality on purpose, so the two numbers legitimately differ.

    What was wrong is narrower: `DISMISSED` listed `cancelled` and the count filtered only
    `rejected` and `errored`, so every cancellation was listed but never counted — 12 of them in
    30 days, measured on dev. Both read `DISMISSED` now.
    """
    await _changeset(reason=DismissalReason.CANCELLED)

    assert (await _row()).dismissed == 1
    page = await get_state_bucket(_STATE, BUCKET_DISMISSED, limit=10)
    assert [r.failure_reason for r in page.rows] == ["cancelled"]


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
async def test_a_run_in_flight_is_counted_before_it_has_a_changeset():
    """The regression. A run mints its changeset at ingest, so while it is still going there is
    no changeset to reach it through — which is every run this count exists to find.

    The two tests above pass either way: their fixture links a changeset by hand, so a
    changeset-rooted lookup finds the run. Only a run built the way production builds one can
    tell the two implementations apart.
    """
    await factories.seed_jurisdiction(_OCDID, _STATE)
    await factories.start_run(_OCDID)

    assert (await _row()).running == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_failed_run_is_counted_as_an_attempt_not_a_proposal():
    """A run that dies mints nothing, so it lands in no changeset column. Before `failed_runs`
    it was in no column at all — a third of scrapes, invisible."""
    await factories.seed_jurisdiction(_OCDID, _STATE)
    run_id = await factories.start_run(_OCDID)
    await factories.fail_run(run_id)

    row = await _row()
    assert row.running == 0
    assert row.failed_runs == 1
    assert (row.to_review, row.published, row.dismissed) == (0, 0, 0)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_failure_that_already_has_a_changeset_is_not_counted_twice():
    """Every run minted before mint-at-ingest carries a changeset, and its failure is already
    reported as a dismissal. Counting it again as a failed attempt would show the same failure in
    two columns of one row — measured on dev, 9 of 10 ERROR runs are in exactly this shape.
    """
    await _changeset(status="ERROR", reason=DismissalReason.ERRORED)

    row = await _row()
    assert row.dismissed == 1
    assert row.failed_runs == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_run_that_reached_ingest_is_a_proposal_not_a_failure():
    """The other half: `complete_run` mints the changeset the way ingest does, so the same run
    leaves the attempt columns and enters the proposal ones."""
    await factories.seed_jurisdiction(_OCDID, _STATE)
    run_id = await factories.start_run(_OCDID)
    await factories.complete_run(run_id)

    row = await _row()
    assert row.running == 0
    assert row.failed_runs == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_calendar_bands_a_day_by_what_became_of_its_runs():
    await _changeset(published=True, days_ago=3)
    await _changeset(reason=DismissalReason.ERRORED, days_ago=3)
    await _changeset(days_ago=3)

    day = next(d for d in await get_state_calendar() if d.state == _STATE and d.published)
    assert (day.published, day.dismissed, day.to_review) == (1, 1, 1)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_calendar_also_says_what_kind_ran():
    """Imports are most of what runs, so a day reading "2 ok" without saying no scraper
    produced them would mislead."""
    await _changeset(published=True, days_ago=4)
    await _changeset(published=True, days_ago=4, kind="sheet_import", status=None)

    day = next(d for d in await get_state_calendar() if d.state == _STATE and d.published == 2)
    assert (day.scrapes, day.imports) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_hand_edit_is_not_a_collection_attempt():
    """`ok` and `failed` describe a run reading a source. A `people_edit` has no run — 8 dev
    rows, none with a status — so counting it would pad the green band with something that
    never ran, and `jurisdiction_edit` could never be "to review" at all."""
    await _changeset(published=True, kind="people_edit", status=None, days_ago=6)

    row = await _row()
    assert row.published == 0
    assert not [d for d in await get_state_calendar() if d.state == _STATE]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_bucket_counts_localities_where_the_rollup_counts_changesets():
    """Deliberately different numbers. One jurisdiction scraped twice is two published runs and
    one place to look at, so the modal's pager must read its total from the bucket — computing
    "+N more" from the rollup would promise rows the list cannot reach."""
    await _changeset(published=True, days_ago=2)
    await _changeset(published=True, days_ago=3)

    assert (await _row()).published == 2
    page = await get_state_bucket(_STATE, BUCKET_PUBLISHED, limit=10)
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

    page = await get_state_bucket(_STATE, BUCKET_DISMISSED, limit=10)
    assert [r.failure_reason for r in page.rows] == ["rejected"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_bucket_returns_nothing_rather_than_everything():
    """The bucket name reaches SQL as a value, so a typo or a stale link must fail closed."""
    await _changeset(published=True)

    page = await get_state_bucket(_STATE, "not-a-bucket", limit=10)
    assert (page.total, page.rows) == (0, [])
