"""Integration tests for `services.sheet_import`.

Against the real test DB, because what is worth checking here is what a mock cannot show: that
sightings and identities land as a pair, that the request lands **unpublished** so the card
reaches the review queue, and that labels actually mint posts.

Run with:
  mise run tcp-integration

Isolation: everything is written under one sentinel jurisdiction, removed before and after each
test. `requests` cascades to `source_records`, so the rows go with it.
"""

from typing import LiteralString
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from core.entry_rows import ImportStatus, parse_rows
from lib.csv import parse_csv
from database import changeset_batches
from database.database import get_pool
from services.batch_review import batch_review, publish_selected
from services.publish import reviewed_file_path
from services.sheet_import import import_rows

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_sheet_test/government"
# A second town, so "one commit for the whole batch" is a claim a test can actually falsify.
_OCDID_2 = "ocd-jurisdiction/country:us/state:zz/place:zz_sheet_test_two/government"
_OCDIDS = [_OCDID, _OCDID_2]
_SHEET = "https://docs.google.com/spreadsheets/d/test/export?format=csv"
_EMAIL = "zz-sheet-import@test.civicpatch.org"


@pytest.fixture(autouse=True)
def batch_commit():
    """Publishing queues its open-data commit on Temporal, which is not running for tests.

    Patched at the enqueue rather than at `promote_batch_to_reviewed`, so the part worth
    checking — which jurisdictions made it in, and what file each renders to — still runs for
    real. Yields the batch enqueue; the single-jurisdiction one is only silenced.
    """
    with (
        patch("lib.temporal.client.enqueue_open_data_commit", new_callable=AsyncMock),
        patch(
            "lib.temporal.client.enqueue_open_data_batch_commit", new_callable=AsyncMock
        ) as enqueued,
    ):
        yield enqueued


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships WHERE post_id IN "
            "(SELECT id FROM posts WHERE jurisdiction_ocdid = ANY(%s))",
            (_OCDIDS,),
        )
        await cur.execute(
            "DELETE FROM posts WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM organizations WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM divisions WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM changesets WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM people WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)", (_OCDIDS,)
        )
        # By owner, not by lock key: a test that starts a second batch picks its own key, and
        # `started_by_user_id` is NOT NULL, so a missed row pins the user below.
        await cur.execute(
            "DELETE FROM changeset_batches WHERE started_by_user_id IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_EMAIL,),
        )
        # Publishing can leave assertions behind, and `assertions.asserted_by` is NOT NULL with
        # no cascade — so the user cannot go until they do.
        await cur.execute(
            "DELETE FROM assertions WHERE asserted_by IN "
            "(SELECT id FROM users WHERE email = %s)",
            (_EMAIL,),
        )
        await cur.execute("DELETE FROM users WHERE email = %s", (_EMAIL,))
        await conn.commit()


@pytest_asyncio.fixture
async def user_id():
    """`requests.created_by_user_id` is a real foreign key — an import is always somebody's."""
    await _cleanup()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state) "
            "SELECT unnest(%s::text[]), 'zz'",
            (_OCDIDS,),
        )
        await cur.execute(
            "INSERT INTO users (email, provider, provider_user_id, role) "
            "VALUES (%s, 'email', %s, 'maintainers') RETURNING id::text",
            (_EMAIL, _EMAIL),
        )
        row = await cur.fetchone()
        assert row is not None
        await conn.commit()
    yield row[0]
    await _cleanup()


@pytest_asyncio.fixture
async def batch_id(user_id):
    """`changesets.batch_id` is a real foreign key, so a literal string will not do."""
    return await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT,
        f"sheet:{_OCDID}",
        user_id,
        {"spreadsheet_id": "test"},
    )


def _sheet_rows(*people, ocdid: str = _OCDID) -> list[dict]:
    return [
        {"jurisdiction_ocdid": ocdid, "name": name, "label": label}
        for name, label in people
    ]


async def _parsed(*people):
    rows, errors = parse_rows(_sheet_rows(*people), _SHEET)
    assert errors == []
    return rows


async def _scalar(sql: LiteralString, params: tuple):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(sql, params)
        row = await cur.fetchone()
    assert row is not None
    return row[0]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_import_writes_sightings_and_lands_in_the_review_queue(
    user_id, batch_id
):
    """The card is raised by the sightings alone — `AVAILABLE_FOR_REVIEW` is
    `EXISTS (source_records for this request)`, so there is no second write and no publish."""
    rows = await _parsed(
        ("Ana Reyes", "Select Board Chair"), ("Bo Chen", "Select Board Member")
    )

    [result] = await import_rows(rows, user_id, batch_id)

    assert result.status is ImportStatus.IMPORTED
    assert result.people == 2
    assert result.sightings == 2

    assert (
        await _scalar(
            "SELECT count(*) FROM source_records WHERE changeset_id = %s::uuid",
            (result.changeset_id,),
        )
        == 2
    )
    # Unpublished: an import proposes a roster, it does not decide one.
    assert (
        await _scalar(
            "SELECT published_at FROM changesets WHERE id = %s::uuid", (result.changeset_id,)
        )
        is None
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_sighting_gets_an_identity(user_id, batch_id):
    """Linkage is written with the evidence, in one transaction — a record with no identity
    would be evidence nothing can find."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, user_id, batch_id)

    assert (
        await _scalar(
            """
            SELECT count(*) FROM source_records sr
            JOIN source_record_identities i ON i.source_record_id = sr.id
            WHERE sr.changeset_id = %s::uuid
            """,
            (result.changeset_id,),
        )
        == 1
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_label_mints_the_post_it_implies(user_id, batch_id):
    """The sheet carries no post id, so the label is the only thing that can imply a seat — and
    projecting it is what makes the 194 MA jurisdictions with no posts importable at all.

    Projected, not created: an import proposes seats like any other changeset, and publishing is
    what mints them. So the count is reported and the table stays empty."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, user_id, batch_id)

    assert result.posts >= 1
    assert (
        await _scalar(
            "SELECT count(*) FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        == 0
    ), "ingest minted a seat; only publishing should"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_batch_is_recorded_on_the_request(user_id, batch_id):
    """So a card can name the import that raised it, and the bulk review screen can ask
    `requests` for this batch's *current* state rather than reading a run-time snapshot."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, user_id, batch_id)

    assert (
        await _scalar(
            "SELECT batch_id::text FROM changesets WHERE id = %s::uuid",
            (result.changeset_id,),
        )
        == batch_id
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_one_jurisdiction_failing_does_not_cost_the_others(user_id, batch_id):
    """Jurisdictions are independent — own request, own sightings. An unknown ocdid violates
    the requests foreign key, and the good one must still import."""
    good, errors = parse_rows(
        _sheet_rows(("Ana Reyes", "Select Board Chair")), _SHEET
    )
    assert errors == []
    missing = "ocd-jurisdiction/country:us/state:zz/place:zz_not_registered/government"
    bad, _ = parse_rows(
        [{"jurisdiction_ocdid": missing, "name": "Cy Diaz", "label": "Chair"}], _SHEET
    )

    results = await import_rows(good + bad, user_id, batch_id)
    by_ocdid = {result.jurisdiction_ocdid: result for result in results}

    assert by_ocdid[_OCDID].status is ImportStatus.IMPORTED
    assert by_ocdid[missing].status is ImportStatus.FAILED
    assert by_ocdid[missing].error


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_from_csv_text(user_id, batch_id):
    """The whole chain a volunteer's sheet actually takes: two tabs of CSV in, a review card out.

    Deliberately includes what a real sheet carries — a header a human typed in mixed case, a
    quoted comma in a name, a jurisdiction nobody ticked, and a row missing its label.
    """
    roster_csv = (
        "Jurisdiction_OCDID,name,label,email\n"
        f'{_OCDID},"Reyes, Ana",Select Board Chair,ana@zz.gov\n'
        f"{_OCDID},Bo Chen,Select Board Member,bo@zz.gov\n"
        f"{_OCDID},Cy Diaz,,cy@zz.gov\n"
    )
    rows, errors = parse_rows(parse_csv(roster_csv), _SHEET)

    # The label-less row is rejected, and takes nobody else with it.
    assert [(error.line, error.column) for error in errors] == [(4, "label")]
    assert len(rows) == 2

    [result] = await import_rows(rows, user_id, batch_id)

    assert result.status is ImportStatus.IMPORTED
    assert result.people == 2
    assert result.posts >= 1
    # A quoted comma survives the whole way to the sighting.
    assert (
        await _scalar(
            "SELECT count(*) FROM source_records WHERE changeset_id = %s::uuid AND name = %s",
            (result.changeset_id, "Reyes, Ana"),
        )
        == 1
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_batch_review_shows_the_towns_it_made(user_id, batch_id):
    """One pass over what the run produced — the limited view, with people from the sightings."""
    rows = await _parsed(
        ("Ana Reyes", "Select Board Chair"), ("Bo Chen", "Select Board Member")
    )
    await import_rows(rows, user_id, batch_id)

    review = await batch_review(batch_id)

    assert review is not None
    [jurisdiction] = review.jurisdictions
    assert jurisdiction.jurisdiction_ocdid == _OCDID
    assert jurisdiction.review_status == "pending"
    assert sorted(person.name for person in jurisdiction.people) == [
        "Ana Reyes",
        "Bo Chen",
    ]
    # The seat, rendered — what makes forty towns scannable.
    assert all(person.label for person in jurisdiction.people)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_an_unknown_batch_reviews_as_nothing(user_id):
    assert await batch_review("00000000-0000-4000-8000-00000000dead") is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_a_selection_leaves_the_rest_pending(user_id, batch_id):
    """The page is a view, not a queue: publishing some does not make the others disappear."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)

    [result] = await publish_selected(batch_id, {_OCDID}, user_id)
    assert result.published is True

    review = await batch_review(batch_id)
    assert review is not None
    [jurisdiction] = review.jurisdictions
    assert jurisdiction.review_status == "published"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_town_nobody_selected_is_left_alone(user_id, batch_id):
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)

    assert await publish_selected(batch_id, set(), user_id) == []

    review = await batch_review(batch_id)
    assert review is not None
    assert review.jurisdictions[0].review_status == "pending"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_twice_does_not_republish(user_id, batch_id):
    """A town already live — published here or from the ordinary queue — is skipped rather than
    superseding itself for nothing."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)
    await publish_selected(batch_id, {_OCDID}, user_id)

    assert await publish_selected(batch_id, {_OCDID}, user_id) == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_two_towns_queues_one_commit(user_id, batch_id, batch_commit):
    """The reviewer published once, so open-data should say so once — not one commit per town.

    Asserted at the enqueue because that is the only place the batching is observable: below it
    is Temporal, above it is a per-jurisdiction loop that looks the same either way.
    """
    rows, errors = parse_rows(
        _sheet_rows(("Ana Reyes", "Select Board Chair"))
        + _sheet_rows(("Bo Nunez", "Town Clerk"), ocdid=_OCDID_2),
        _SHEET,
    )
    assert errors == []
    await import_rows(rows, user_id, batch_id)

    results = await publish_selected(batch_id, set(_OCDIDS), user_id)
    assert [result.published for result in results] == [True, True]

    batch_commit.assert_awaited_once()
    request = batch_commit.await_args.args[0]
    assert request.batch_id == batch_id
    assert {item.jurisdiction_ocdid for item in request.items} == set(_OCDIDS)
    assert {item.file_path for item in request.items} == {
        reviewed_file_path(_OCDID),
        reviewed_file_path(_OCDID_2),
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_town_that_refused_to_publish_stays_out_of_the_commit(
    user_id, batch_id, batch_commit
):
    """One jurisdiction failing must not keep the others out of open-data, and must not put
    itself in — the commit covers what reached the database, not what was selected."""
    rows, errors = parse_rows(
        _sheet_rows(("Ana Reyes", "Select Board Chair"))
        + _sheet_rows(("Bo Nunez", "Town Clerk"), ocdid=_OCDID_2),
        _SHEET,
    )
    assert errors == []
    await import_rows(rows, user_id, batch_id)

    with patch(
        "services.batch_review.roster_edits.publish_to_database",
        new_callable=AsyncMock,
        side_effect=[RuntimeError("supersede guard"), None],
    ):
        results = await publish_selected(batch_id, set(_OCDIDS), user_id)

    assert sorted(result.published for result in results) == [False, True]
    [item] = batch_commit.await_args.args[0].items
    published = next(result for result in results if result.published)
    assert item.jurisdiction_ocdid == published.jurisdiction_ocdid


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_nothing_queues_no_commit(user_id, batch_id, batch_commit):
    """An empty commit is not a record of anything."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)

    assert await publish_selected(batch_id, set(), user_id) == []
    batch_commit.assert_not_awaited()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_running_import_is_findable_without_being_remembered(
    user_id, batch_id
):
    """Whoever opens the page finds the import under way — there is one spreadsheet and one
    lock, so it is a fact about the system, not about the browser that started it."""
    found = await changeset_batches.latest(changeset_batches.BatchKind.SHEET_IMPORT)

    assert found is not None
    assert found["id"] == batch_id
    assert found["status"] == changeset_batches.BatchStatus.RUNNING


@pytest.mark.integration
@pytest.mark.asyncio
async def test_publishing_dismisses_the_cards_it_makes_pointless(
    user_id, batch_id, batch_commit
):
    """Two imports minutes apart leave two cards for one locality. Publishing the newer one
    makes the older obviously stale, and it used to sit in the queue until a timed sweep
    noticed — offering a reviewer a card that could only ever refuse."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))
    await import_rows(rows, user_id, batch_id)
    older = await _scalar(
        "SELECT id::text FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
    )

    # A second import of the same locality, which is what a re-run produces.
    second = await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT,
        f"sheet:{_OCDID}:again",
        user_id,
        {"spreadsheet_id": "test"},
    )
    await import_rows(await _parsed(("Bo Nunez", "Town Clerk")), user_id, second)

    [result] = await publish_selected(second, {_OCDID}, user_id)
    assert result.published is True

    assert (
        await _scalar(
            "SELECT dismissed_reason FROM changesets WHERE id = %s", (older,)
        )
        == "superseded"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_one_sheet_cannot_have_two_imports_at_once(user_id, batch_id):
    """Enforced by a partial unique index, not by application code checking first — a
    check-then-insert has a window two callers can both pass through.

    Two runs over one sheet would each raise a review card per locality, which is how a single
    import turns into duplicate cards nobody can tell apart.
    """
    with pytest.raises(changeset_batches.BatchAlreadyRunning):
        await changeset_batches.start(
            changeset_batches.BatchKind.SHEET_IMPORT,
            f"sheet:{_OCDID}",
            user_id,
            {"spreadsheet_id": "test"},
        )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_lock_lifts_when_the_batch_finishes(user_id, batch_id):
    """The index is partial on `finished_at IS NULL`, and `run_import` stamps it on success and
    failure alike — so the sheet frees itself for the next run either way."""
    await changeset_batches.finish(batch_id, changeset_batches.BatchStatus.SUCCEEDED)

    again = await changeset_batches.start(
        changeset_batches.BatchKind.SHEET_IMPORT,
        f"sheet:{_OCDID}",
        user_id,
        {"spreadsheet_id": "test"},
    )
    assert again != batch_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_locality_the_sheet_says_is_handled_raises_no_second_card(
    user_id, batch_id
):
    """Re-reading a sheet nobody has touched should do nothing. It used to raise a duplicate
    card per locality per run and lean on supersede to tidy up: six runs on dev left Centralia
    with five cards, four swept and one published."""
    rows, errors = parse_rows(
        _sheet_rows(("Ana Reyes", "Select Board Chair")), _SHEET
    )
    assert errors == []
    for row in rows:
        row.status = ImportStatus.IMPORTED

    results = await import_rows(rows, user_id, batch_id)

    assert [result.status for result in results] == [ImportStatus.UNCHANGED]
    assert results[0].changeset_id is None
    assert (
        await _scalar(
            "SELECT count(*) FROM changesets WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        == 0
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clearing_one_row_brings_the_whole_roster_back(user_id, batch_id):
    """Whole, not just the cleared row: a card carrying one of two people would propose closing
    the other's membership when published."""
    rows, errors = parse_rows(
        _sheet_rows(("Ana Reyes", "Select Board Chair"), ("Bo Chen", "Town Clerk")),
        _SHEET,
    )
    assert errors == []
    rows[0].status = ImportStatus.IMPORTED
    rows[1].status = ""

    [result] = await import_rows(rows, user_id, batch_id)

    assert result.status is ImportStatus.IMPORTED
    assert (
        await _scalar(
            "SELECT count(*) FROM source_records WHERE changeset_id = %s::uuid",
            (result.changeset_id,),
        )
        == 2
    )
