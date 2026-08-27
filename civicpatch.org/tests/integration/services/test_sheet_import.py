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

import pytest
import pytest_asyncio

from core.entry_rows import parse_rows, ready_jurisdictions
from lib.csv import parse_csv
from database import request_batches
from database.database import get_pool
from services.sheet_import import Disposition, import_rows

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_sheet_test/government"
_SHEET = "https://docs.google.com/spreadsheets/d/test/export?format=csv"
_EMAIL = "zz-sheet-import@test.civicpatch.org"


async def _cleanup():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships WHERE post_id IN "
            "(SELECT id FROM posts WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        await cur.execute("DELETE FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute(
            "DELETE FROM organizations WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute("DELETE FROM divisions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM requests WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute("DELETE FROM people WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await cur.execute("DELETE FROM request_batches WHERE lock_key = %s", (f"sheet:{_OCDID}",))
        await cur.execute("DELETE FROM users WHERE email = %s", (_EMAIL,))
        await conn.commit()


@pytest_asyncio.fixture
async def user_id():
    """`requests.requested_by_user_id` is a real foreign key — an import is always somebody's."""
    await _cleanup()
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state) VALUES (%s, 'zz')",
            (_OCDID,),
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
    """`requests.batch_id` is a real foreign key, so a literal string will not do."""
    return await request_batches.start(
        request_batches.BatchKind.SHEET_IMPORT,
        f"sheet:{_OCDID}",
        user_id,
        {"spreadsheet_id": "test"},
    )


def _sheet_rows(*people) -> list[dict]:
    return [
        {"jurisdiction_ocdid": _OCDID, "name": name, "label": label}
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

    [result] = await import_rows(rows, {_OCDID}, user_id, batch_id)

    assert result.disposition is Disposition.IMPORTED
    assert result.people == 2
    assert result.sightings == 2

    assert (
        await _scalar(
            "SELECT count(*) FROM source_records WHERE request_id = %s::uuid",
            (result.request_id,),
        )
        == 2
    )
    # Unpublished: an import proposes a roster, it does not decide one.
    assert (
        await _scalar(
            "SELECT published_at FROM requests WHERE id = %s::uuid", (result.request_id,)
        )
        is None
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_sighting_gets_an_identity(user_id, batch_id):
    """Linkage is written with the evidence, in one transaction — a record with no identity
    would be evidence nothing can find."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, {_OCDID}, user_id, batch_id)

    assert (
        await _scalar(
            """
            SELECT count(*) FROM source_records sr
            JOIN source_record_identities i ON i.source_record_id = sr.id
            WHERE sr.request_id = %s::uuid
            """,
            (result.request_id,),
        )
        == 1
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_label_mints_the_post_it_implies(user_id, batch_id):
    """The sheet carries no post id, so this is the only way a seat comes into being — and it
    is what makes the 194 MA jurisdictions with no posts importable at all."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, {_OCDID}, user_id, batch_id)

    assert result.posts >= 1
    assert (
        await _scalar(
            "SELECT count(*) FROM posts WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        >= 1
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_a_jurisdiction_nobody_marked_ready_is_skipped(user_id, batch_id):
    """Only the volunteer knows a town is finished. Without the tick nothing is written — no
    request, so no card for half-typed work."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, set(), user_id, batch_id)

    assert result.disposition is Disposition.SKIPPED
    assert result.request_id is None
    assert (
        await _scalar(
            "SELECT count(*) FROM requests WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        == 0
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_the_batch_is_recorded_on_the_request(user_id, batch_id):
    """So a card can name the import that raised it, and the bulk review screen can ask
    `requests` for this batch's *current* state rather than reading a run-time snapshot."""
    rows = await _parsed(("Ana Reyes", "Select Board Chair"))

    [result] = await import_rows(rows, {_OCDID}, user_id, batch_id)

    assert (
        await _scalar(
            "SELECT batch_id::text FROM requests WHERE id = %s::uuid",
            (result.request_id,),
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

    results = await import_rows(good + bad, {_OCDID, missing}, user_id, batch_id)
    by_ocdid = {result.jurisdiction_ocdid: result for result in results}

    assert by_ocdid[_OCDID].disposition is Disposition.IMPORTED
    assert by_ocdid[missing].disposition is Disposition.FAILED
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
    jurisdictions_csv = f"jurisdiction_ocdid,ready\n{_OCDID},TRUE\n"

    rows, errors = parse_rows(parse_csv(roster_csv), _SHEET)
    ready = ready_jurisdictions(parse_csv(jurisdictions_csv))

    # The label-less row is rejected, and takes nobody else with it.
    assert [(error.line, error.column) for error in errors] == [(4, "label")]
    assert len(rows) == 2

    [result] = await import_rows(rows, ready, user_id, batch_id)

    assert result.disposition is Disposition.IMPORTED
    assert result.people == 2
    assert result.posts >= 1
    # A quoted comma survives the whole way to the sighting.
    assert (
        await _scalar(
            "SELECT count(*) FROM source_records WHERE request_id = %s::uuid AND name = %s",
            (result.request_id, "Reyes, Ana"),
        )
        == 1
    )
